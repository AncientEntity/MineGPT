# MineGPT

Take a book and quill, write what you want to happen in minecraft, and then name it "gpt". The plugin will generate the necessary command block code then execute it for you.

## Setup

Release is for 1.18.2. Should compile to 1.19.x.
Sometimes the ChatGPT proxy runs out of monthly quota, if this occurs you'll have to run a GPT server locally. Luckily it's free to run. All you need is Python 3.X, Playwright and a ChatGPT account.
Here's how to setup a local server if needed:
1. Install python (Python.org) Tested with python 3.9 but any Python 3.X should work.
2. CMD: `pip install git+https://github.com/mmabrouk/chatgpt-wrapper`
3. CMD: `playwright install firefox` (Previous command also installs playwright)
4. CMD: `chatgpt install` (will open a firefox browser, you'll have to log into chatgpt with your account once and it'll remember it)
5. Now just run the "chatgptwebproxy.py" file while the plugin is running.
6. If it is still trying to use the external proxy use `/gpt proxy` or `/gpt local` to toggle it to your local proxy.

## Features


Commands:
/gpt
  - /gpt kill - stops current GPT
  - /gpt proxy or /gpt local will toggle if the plugin uses a local proxy server.


By default the plugin only looks at the first page of any book.

Example Prompts To Try:
1. When an arrow is stuck on the ground spawn a primed tnt and after that remove the arrow
2. Kill all entities within a 3 block radius of any arrow except for players and arrows.
3. Remove all blocks around all arrows in a radius 3 sphere and replace it with air. Don't destroy the arrow.
4. Remove all blocks around all players in a radius 3 sphere and replace it with air
5. Every tick summon a bat at an arrow
6. When any player holds a diamond, put a diamond block below them.
7. Change all grass to netherrack in a radius around any player. Change all water to lava in a radius around any player. Change all dirt to netherrack in a radius around any player. Change all sand and stone to soul sand in a radius around any player.
8. Spawn a TNT on every item entity (Grey Goo Scenario)

## License

This is under the MIT license, however, we are using chatgpt-wrapper (for the local proxy), which is also under it's own MIT license [viewable here](https://github.com/mmabrouk/chatgpt-wrapper/blob/main/License)


