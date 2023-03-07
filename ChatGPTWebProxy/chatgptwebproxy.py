from chatgpt_wrapper import ChatGPT
from chatgpt_wrapper.config import Config
import socket
import atexit

config = None
gpt = None

def exit_handler():
    if(gpt != None):
        gpt.delete_conversation()
        print("GPT Conversation Deleted...")
atexit.register(exit_handler)

def request(prompt,gpt):
    #config.set('browser.debug', True)
    response1 = gpt.ask(prompt)
    return response1

if __name__ == '__main__':
    config = Config()
    gpt = ChatGPT(config)

    s = socket.socket()
    s.bind(("127.0.0.1",23484))
    s.listen(1)

    print("GPT Web Proxy Server Listening")

    lastPrompt = ""

    while True:
        conn, addr = s.accept()
        with conn:
            recv = conn.recv(2048).decode()
            print("Request: "+recv)
            response = ""
            for attempt in range(3):
                try:

                    if(recv == lastPrompt):
                        gpt.delete_conversation()
                        gpt = ChatGPT(config)

                    response = request(recv,gpt)
                    break
                except:
                    pass
            print("Recieved: "+response)
            conn.send(response.encode())
            conn.close()