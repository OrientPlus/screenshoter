import uvicorn
from producer.server import Server

server = Server()
app = server.app

if __name__ == "__main__":
    uvicorn.run("producer.main:app", host="0.0.0.0", port=8000, reload=False)
