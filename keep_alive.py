from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ GIO.DOT002 is alive and running!"

def run():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    threading.Thread(target=run).start()
