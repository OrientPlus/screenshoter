import uvicorn
from os import getenv
from producer.server import Server

server = Server()
app = server.app

if __name__ == "__main__":
    host = getenv("HOST", "0.0.0.0")
    port = int(getenv("PORT", 8000))
    uvicorn.run("producer.main:app", host=host, port=port, reload=False)
