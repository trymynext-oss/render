from flask import Flask, request
import subprocess
import os

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    output = ""
    if request.method == "POST":
        cmd = request.form.get("cmd")
        if cmd:
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                output = result.stdout + result.stderr
            except Exception as e:
                output = str(e)

    return f"""
    <form method="post">
      <input name="cmd" style="width:400px" placeholder="echo hello" />
      <button>Run</button>
    </form>
    <pre>{output}</pre>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
