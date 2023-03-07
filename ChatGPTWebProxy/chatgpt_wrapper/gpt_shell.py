import re
import textwrap
import yaml
import os
import platform
import sys
import datetime
import subprocess

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
# from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.styles import Style
import prompt_toolkit.document as document

from rich.console import Console
from rich.markdown import Markdown

from chatgpt_wrapper.config import Config
from chatgpt_wrapper.logger import Logger
import chatgpt_wrapper.constants as constants

console = Console()

is_windows = platform.system() == "Windows"

# Monkey patch _FIND_WORD_RE in the document module.
# This is needed because the current version of _FIND_WORD_RE
# doesn't allow any special characters in the first word, and we need
# to start commands with a special character.
# It would also be possible to subclass NesteredCompleter and override
# the get_completions() method, but that feels more brittle.
document._FIND_WORD_RE = re.compile(r"([a-zA-Z0-9_" + constants.COMMAND_LEADER + r"]+|[^a-zA-Z0-9_\s]+)")
# I think this 'better' regex should work, but it's not.
# document._FIND_WORD_RE = re.compile(r"(\/|\/?[a-zA-Z0-9_]+|[^a-zA-Z0-9_\s]+)")

class LegacyCommandLeaderError(Exception):
    pass

class NoInputError(Exception):
    pass

class GPTShell():
    """
    A shell interpreter that serves as a front end to the ChatGPT class
    """

    intro = "Provide a prompt for ChatGPT, or type %shelp or ? to list commands." % constants.COMMAND_LEADER
    prompt = "> "
    doc_header = "Documented commands type %shelp [command without %s] (e.g. /help ask) for detailed help" % (constants.COMMAND_LEADER, constants.COMMAND_LEADER)

    # our stuff
    prompt_number = 0
    chatgpt = None
    message_map = {}
    stream = False
    logfile = None

    def __init__(self, config=None):
        self.config = config or Config()
        self.log = Logger(self.__class__.__name__, self.config)
        self.configure_commands()
        self.command_completer = self.get_command_completer()
        self.history = self.get_history()
        self.style = self.get_styles()
        self.prompt_session = PromptSession(
            history=self.history,
            # NOTE: Suggestions from history don't seem like a good fit for this REPL,
            # so we don't use it. Leaving it here for reference.
            # auto_suggest=AutoSuggestFromHistory(),
            completer=self.command_completer,
            style=self.style
        )
        self.stream = self.config.get('chat.streaming')
        self._set_logging()

    def configure_commands(self):
        self.commands = [method[3:] for method in dir(__class__) if callable(getattr(__class__, method)) and method.startswith("do_")]

    def get_command_completer(self):
        commands_with_leader = {"%s%s" % (constants.COMMAND_LEADER, key): None for key in self.commands}
        commands_with_leader["%shelp" % constants.COMMAND_LEADER] = {key: None for key in self.commands}
        completer = NestedCompleter.from_nested_dict(commands_with_leader)
        return completer

    def get_history(self):
        return FileHistory(constants.COMMAND_HISTORY_FILE)

    def get_styles(self):
        style = Style.from_dict({
            'completion-menu.completion': 'bg:#008888 #ffffff',
            'completion-menu.completion.current': 'bg:#00aaaa #000000',
            'scrollbar.background': 'bg:#88aaaa',
            'scrollbar.button': 'bg:#222222',
        })
        return style

    def legacy_command_leader_warning(self, command):
        print("\nWarning: The legacy command leader '%s' has been removed.\n"
              "Use the new command leader '%s' instead, e.g. %s%s\n" % (
                  constants.LEGACY_COMMAND_LEADER, constants.COMMAND_LEADER, constants.COMMAND_LEADER, command))

    def get_command_help_brief(self, command):
        help_brief = "    %s%s" % (constants.COMMAND_LEADER, command)
        help_doc = self.get_command_help(command)
        if help_doc:
            first_line = next(filter(lambda x: x.strip(), help_doc.splitlines()), "")
            help_brief += ": %s" % first_line
        return help_brief

    def get_command_help(self, command):
        if command in self.commands:
            method = self.get_command_method(command)
            doc = method.__doc__
            if doc:
                help_text = doc.replace("{leader}", constants.COMMAND_LEADER)
                return textwrap.dedent(help_text)

    def help_commands(self):
        print("")
        self._print_markdown(f"#### {self.doc_header}")
        print("")
        for command in self.commands:
            print(self.get_command_help_brief(command))
        print("")

    def help(self, command=''):
        if command:
            help_doc = self.get_command_help(command)
            if help_doc:
                print(help_doc)
            else:
                print("\nNo help for '%s'\n\nAvailable commands: %s" % (command, ", ".join(self.commands)))
        else:
            self.help_commands()

    def _set_logging(self):
        if self.config.get('chat.log.enabled'):
            log_file = self.config.get('chat.log.filepath')
            if log_file:
                if not self._open_log(log_file):
                    print("\nERROR: could not open log file: %s" % log_file)
                    sys.exit(0)

    def _set_prompt(self):
        self.prompt = f"{self.prompt_number}> "

    def _update_message_map(self):
        self.prompt_number += 1
        self.message_map[self.prompt_number] = (
            self.backend.conversation_id,
            self.backend.parent_message_id,
        )
        self._set_prompt()

    def _print_markdown(self, output):
        console.print(Markdown(output))
        print("")

    def _write_log(self, prompt, response):
        if self.logfile is not None:
            self.logfile.write(f"{self.prompt_number}> {prompt}\n\n{response}\n\n")
            self._write_log_context()

    def _write_log_context(self):
        if self.logfile is not None:
            self.logfile.write(
                f"## context {self.backend.conversation_id}:{self.backend.parent_message_id}\n"
            )
            self.logfile.flush()

    def _parse_conversation_ids(self, id_string):
        items = [item.strip() for item in id_string.split(',')]
        final_list = []
        for item in items:
            if len(item) == 36:
                final_list.append(item)
            else:
                sub_items = item.split('-')
                try:
                    sub_items = [int(item) for item in sub_items if int(item) >= 1 and int(item) <= constants.DEFAULT_HISTORY_LIMIT]
                except ValueError:
                    return "Error: Invalid range, must be two ordered history numbers separated by '-', e.g. '1-10'."
                if len(sub_items) == 1:
                    final_list.extend(sub_items)
                elif len(sub_items) == 2 and sub_items[0] < sub_items[1]:
                    final_list.extend(list(range(sub_items[0], sub_items[1] + 1)))
                else:
                    return "Error: Invalid range, must be two ordered history numbers separated by '-', e.g. '1-10'."
        return list(set(final_list))

    async def configure_backend():
        raise NotImplementedError

    async def setup(self):
        await self.configure_backend()
        self._update_message_map()

    async def cleanup(self):
        pass

    async def _fetch_history(self, limit=constants.DEFAULT_HISTORY_LIMIT, offset=0):
        self._print_markdown("* Fetching conversation history...")
        history = await self.backend.get_history(limit=limit, offset=offset)
        return history

    async def _set_title(self, title, conversation_id=None):
        self._print_markdown("* Setting title...")
        if await self.backend.set_title(title, conversation_id):
            self._print_markdown("* Title set to: %s" % title)

    async def _delete_conversation(self, id, label=None):
        if id == self.backend.conversation_id:
            await self._delete_current_conversation()
        else:
            label = label or id
            self._print_markdown("* Deleting conversation: %s" % label)
            if await self.backend.delete_conversation(id):
                self._print_markdown("* Deleted conversation: %s" % label)

    async def _delete_current_conversation(self):
        self._print_markdown("* Deleting current conversation")
        if await self.backend.delete_conversation():
            self._print_markdown("* Deleted current conversation")
            await self.do_new(None)

    async def do_stream(self, _):
        """
        Toggle streaming mode

        Streaming mode: streams the raw response from ChatGPT (no markdown rendering)
        Non-streaming mode: Returns full response at completion (markdown rendering supported).

        Examples:
            {leader}stream
        """
        self.stream = not self.stream
        self._print_markdown(
            f"* Streaming mode is now {'enabled' if self.stream else 'disabled'}."
        )

    async def do_new(self, _):
        """
        Start a new conversation

        Examples:
            {leader}new
        """
        self.backend.new_conversation()
        self._print_markdown("* New conversation started.")
        self._update_message_map()
        self._write_log_context()

    async def do_delete(self, arg):
        """
        Delete one or more conversations

        Can delete by conversation ID, history ID, or current conversation.

        Arguments:
            conversation_id: The ID of the conversation
            history_id : The history ID

        Arguments can be mixed and matched as in the examples below.

        Examples:
            Current conversation: {leader}delete
            By conversation ID: {leader}delete 5eea79ce-b70e-11ed-b50e-532160c725b2
            By history ID: {leader}delete 3
            Multiple IDs: {leader}delete 1,5
            Ranges: {leader}delete 1-5
            Complex: {leader}delete 1,3-5,5eea79ce-b70e-11ed-b50e-532160c725b2
        """
        if arg:
            result = self._parse_conversation_ids(arg)
            if isinstance(result, list):
                history = await self._fetch_history()
                if history:
                    history_list = [h for h in history.values()]
                    for item in result:
                        if isinstance(item, str) and len(item) == 36:
                            await self._delete_conversation(item)
                        else:
                            if item <= len(history_list):
                                conversation = history_list[item - 1]
                                await self._delete_conversation(conversation['id'], conversation['title'])
                            else:
                                self._print_markdown("* Cannont delete history item %d, does not exist" % item)
            else:
                self._print_markdown(result)
        else:
            await self._delete_current_conversation()

    async def do_history(self, arg):
        """
        Show recent conversation history

        Arguments;
            limit: limit the number of messages to show (default 20)
            offset: offset the list of messages by this number

        Examples:
            {leader}history
            {leader}history 10
            {leader}history 10 5
        """
        limit = constants.DEFAULT_HISTORY_LIMIT
        offset = 0
        if arg:
            args = arg.split(' ')
            if len(args) > 2:
                self._print_markdown("* Invalid number of arguments, must be limit [offest]")
                return
            else:
                try:
                    limit = int(args[0])
                except ValueError:
                    self._print_markdown("* Invalid limit, must be an integer")
                    return
                if len(args) == 2:
                    try:
                        offset = int(args[1])
                    except ValueError:
                        self._print_markdown("* Invalid offset, must be an integer")
                        return
        history = await self._fetch_history(limit=limit, offset=offset)
        if history:
            history_list = [h for h in history.values()]
            self._print_markdown("## Recent history:\n\n%s" % "\n".join(["1. %s: %s (%s)" % (datetime.datetime.strptime(h['create_time'], "%Y-%m-%dT%H:%M:%S.%f").strftime("%Y-%m-%d %H:%M"), h['title'], h['id']) for h in history_list]))

    async def do_nav(self, arg):
        """
        Navigate to a past point in the conversation

        Arguments:
            id: prompt ID

        Examples:
            {leader}nav 2
        """

        try:
            msg_id = int(arg)
        except Exception:
            self._print_markdown("The argument to nav must be an integer.")
            return

        if msg_id == self.prompt_number:
            self._print_markdown("You are already using prompt {msg_id}.")
            return

        if msg_id not in self.message_map:
            self._print_markdown(
                "The argument to `nav` contained an unknown prompt number."
            )
            return
        elif self.message_map[msg_id][0] is None:
            self._print_markdown(
                f"Cannot navigate to prompt number {msg_id}, no conversation present, try next prompt."
            )
            return

        (
            self.backend.conversation_id,
            self.backend.parent_message_id,
        ) = self.message_map[msg_id]
        self._update_message_map()
        self._write_log_context()
        self._print_markdown(
            f"* Prompt {self.prompt_number} will use the context from prompt {arg}."
        )

    async def do_title(self, arg):
        """
        Show or set title

        Arguments:
            title: title of the current conversation
            ...or...
            history_id: history ID of conversation

        Examples:
            Get current conversation title: {leader}title
            Set current conversation title: {leader}title new title
            Set conversation title using history ID: {leader}title 1
        """
        if arg:
            history = await self._fetch_history()
            history_list = [h for h in history.values()]
            conversation_id = None
            id = None
            try:
                id = int(arg)
            except Exception:
                pass
            if id:
                if id <= len(history_list):
                    conversation_id = history_list[id - 1]["id"]
                else:
                    self._print_markdown("* Cannot set title on history item %d, does not exist" % id)
                    return
            if conversation_id:
                new_title = input("Enter new title for '%s': " % history[conversation_id]["title"])
            else:
                new_title = arg
            await self._set_title(new_title, conversation_id)
        else:
            if self.backend.conversation_id:
                history = await self._fetch_history()
                if self.backend.conversation_id in history:
                    self._print_markdown("* Title: %s" % history[self.backend.conversation_id]['title'])
                else:
                    self._print_markdown("* Cannot load conversation title, not in history.")
            else:
                self._print_markdown("* Current conversation has no title, you must send information first")

    async def do_chat(self, arg):
        """
        Retrieve chat content

        Arguments:
            conversation_id: The ID of the conversation
            ...or...
            history_id: The history ID

        Examples:
            By conversation ID: {leader}chat 5eea79ce-b70e-11ed-b50e-532160c725b2
            By history ID: {leader}chat 2
        """
        conversation_id = None
        title = None
        if arg:
            if len(arg) == 36:
                conversation_id = arg
                title = arg
            else:
                history = await self._fetch_history()
                history_list = [h for h in history.values()]
                id = None
                try:
                    id = int(arg)
                except Exception:
                    self._print_markdown("* Invalid chat history item %d, must be in integer" % id)
                    return
                if id:
                    if id <= len(history_list):
                        conversation_id = history_list[id - 1]["id"]
                        title = history_list[id - 1]["title"]
                    else:
                        self._print_markdown("* Cannot retrieve chat content on history item %d, does not exist" % id)
                        return
        else:
            if not self.backend.conversation_id:
                self._print_markdown("* Current conversation is empty, you must send information first")
                return
        conversation_data = await self.backend.get_conversation(conversation_id)
        if conversation_data:
            messages = self.backend.conversation_data_to_messages(conversation_data)
            if title:
                self._print_markdown(f"### {title}")
            self._print_markdown(self._conversation_from_messages(messages))
        else:
            self._print_markdown("* Could not load chat content")

    async def do_switch(self, arg):
        """
        Switch to chat

        Arguments:
            conversation_id: The ID of the conversation
            ...or...
            history_id: The history ID

        Examples:
            By conversation ID: {leader}switch 5eea79ce-b70e-11ed-b50e-532160c725b2
            By history ID: {leader}switch 2
        """
        conversation_id = None
        title = None
        if arg:
            if len(arg) == 36:
                conversation_id = arg
                title = arg
            else:
                history = await self._fetch_history()
                history_list = [h for h in history.values()]
                id = None
                try:
                    id = int(arg)
                except Exception:
                    self._print_markdown(f"* Invalid chat history item {id}, must be in integer")
                    return
                if id:
                    if id <= len(history_list):
                        conversation_id = history_list[id - 1]["id"]
                        title = history_list[id - 1]["title"]
                    else:
                        self._print_markdown("* Cannot retrieve chat content on history item %d, does not exist" % id)
                        return
        else:
            self._print_markdown("* Argument required, ID or history ID")
            return
        if conversation_id and conversation_id == self.backend.conversation_id:
            self._print_markdown("* You are already in chat: %s" % title)
            return
        conversation_data = await self.backend.get_conversation(conversation_id)
        if conversation_data:
            messages = self.backend.conversation_data_to_messages(conversation_data)
            message = messages.pop()
            self.backend.conversation_id = conversation_id
            self.backend.parent_message_id = message['id']
            self._update_message_map()
            self._write_log_context()
            if title:
                self._print_markdown(f"### Switched to: {title}")
        else:
            self._print_markdown("* Could not switch to chat")

    async def do_ask(self, line):
        """
        Ask a question to ChatGPT

        It is purely optional.

        Examples:
            {leader}ask what is 6+6 (is the same as 'what is 6+6')
        """
        return await self.default(line)

    async def default(self, line):
        if not line:
            return

        if self.stream:
            response = ""
            first = True
            async for chunk in self.backend.ask_stream(line):
                if first:
                    print("")
                    first = False
                print(chunk, end="")
                sys.stdout.flush()
                response += chunk
            print("\n")
        else:
            response = await self.backend.ask(line)
            print("")
            self._print_markdown(response)

        self._write_log(line, response)
        self._update_message_map()

    async def do_read(self, _):
        """
        Begin reading multi-line input

        Allows for entering more complex multi-line input prior to sending it to ChatGPT.

        Examples:
            {leader}read
        """
        ctrl_sequence = "^z" if is_windows else "^d"
        self._print_markdown(f"* Reading prompt, hit {ctrl_sequence} when done, or write line with /end.")

        prompt = ""
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line == "":
                print("")
            if line == "/end":
                break
            prompt += line + "\n"

        await self.default(prompt)

    async def do_editor(self, args):
        """
        Open an editor for entering a command

        When the editor is closed, the content is sent to ChatGPT.

        Requires 'vipe' executable in your path.

        Arguments:
            default_text: The default text to open the editor with

        Examples:
            {leader}editor
            {leader}editor some text to start with
        """
        try:
            process = subprocess.Popen(['vipe'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        except FileNotFoundError:
            self._print_markdown(
                "Failed to execute `vipe`, must be installed and in path. Install package `moreutils`. `brew install moreutils` on macOS and `apt install moreutils` on Ubuntu.")
            return
        process.stdin.write(args.encode())
        process.stdin.close()
        process.wait()
        output = process.stdout.read().decode()
        print(output)
        await self.default(output)

    async def do_file(self, arg):
        """
        Send a prompt read from the named file

        Arguments:
            file_name: The name of the file to read from

        Examples:
            {leader}file myprompt.txt
        """
        try:
            fileprompt = open(arg, encoding="utf-8").read()
        except Exception:
            self._print_markdown(f"Failed to read file '{arg}'")
            return
        await self.default(fileprompt)

    def _open_log(self, filename) -> bool:
        try:
            if os.path.isabs(filename):
                self.logfile = open(filename, "a", encoding="utf-8")
            else:
                self.logfile = open(os.path.join(os.getcwd(), filename), "a", encoding="utf-8")
        except Exception:
            self._print_markdown(f"Failed to open log file '{filename}'.")
            return False
        return True

    async def do_log(self, arg):
        """
        Enable/disable logging to a file

        Arguments:
            file_name: The name of the file to write to

        Examples:
            Log to file: {leader}log mylog.txt
            Disable logging: {leader}log
        """
        if arg:
            if self._open_log(arg):
                self._print_markdown(f"* Logging enabled, appending to '{arg}'.")
        else:
            self.logfile = None
            self._print_markdown("* Logging is now disabled.")

    async def do_context(self, arg):
        """
        Load an old context from the log

        Arguments:
            context_string: a context string from logs

        Examples:
            {leader}context 67d1a04b-4cde-481e-843f-16fdb8fd3366:0244082e-8253-43f3-a00a-e2a82a33cba6
        """
        try:
            (conversation_id, parent_message_id) = arg.split(":")
            assert conversation_id == "None" or len(conversation_id) == 36
            assert len(parent_message_id) == 36
        except Exception:
            self._print_markdown("Invalid parameter to `context`.")
            return
        self._print_markdown("* Loaded specified context.")
        self.backend.conversation_id = (
            conversation_id if conversation_id != "None" else None
        )
        self.backend.parent_message_id = parent_message_id
        self._update_message_map()
        self._write_log_context()

    async def do_config(self, _):
        """
        Show the current configuration

        Examples:
            {leader}config
        """
        output = """
## Configuration

* Config dir: %s
* Profile: %s (as %s.yaml)
* Data dir: %s

```
%s
```
        """ % (self.config.config_dir, self.config.profile, self.config.profile, self.config.data_dir, yaml.dump(self.config.get(), default_flow_style=False))
        self._print_markdown(output)

    async def do_exit(self, _):
        """
        Exit the ChatGPT shell

        Examples:
            {leader}exit
        """
        pass

    async def do_quit(self, _):
        """
        Exit the ChatGPT shell

        Examples:
            {leader}quit
        """
        pass

    def parse_shell_input(self, user_input):
        text = user_input.strip()
        if not text:
            raise NoInputError
        leader = text[0]
        if leader == constants.COMMAND_LEADER or leader == constants.LEGACY_COMMAND_LEADER:
            text = text[1:]
            parts = [arg.strip() for arg in text.split(maxsplit=1)]
            command = parts[0]
            argument = parts[1] if len(parts) > 1 else ''
            if leader == constants.LEGACY_COMMAND_LEADER:
                self.legacy_command_leader_warning(command)
                raise LegacyCommandLeaderError
            if command == "exit" or command == "quit":
                raise EOFError
        else:
            if text == '?':
                command = 'help'
                argument = ''
            else:
                command = constants.DEFAULT_COMMAND
                argument = text
        return command, argument

    def get_command_method(self, command):
        do_command = f"do_{command}"
        for klass in self.__class__.__mro__:
            method = getattr(klass, do_command, None)
            if method:
                return method
        raise AttributeError(f"{do_command} method not found in any shell class")

    async def run_command(self, command, argument):
        if command == 'help':
            self.help(argument)
        else:
            if command in self.commands:
                method = self.get_command_method(command)
                try:
                    response = await method(self, argument)
                except Exception as e:
                    print(repr(e))
                else:
                    if response:
                        print(response)
            else:
                print(f'Unknown command: {command}')

    async def cmdloop(self):
        print("")
        self._print_markdown("### %s" % self.intro)
        while True:
            try:
                user_input = await self.prompt_session.prompt_async(self.prompt)
            except KeyboardInterrupt:
                continue  # Control-C pressed. Try again.
            except EOFError:
                break  # Control-D pressed.
            try:
                command, argument = self.parse_shell_input(user_input)
            except (NoInputError, LegacyCommandLeaderError):
                continue
            except EOFError:
                break
            await self.run_command(command, argument)
        print('GoodBye!')
