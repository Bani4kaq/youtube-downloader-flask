import os
import uuid
import shutil
import tempfile
from flask import Flask, render_template, request, send_file, jsonify

import yt_dlp

app = Flask(__name__)

# All downloads live under a temp dir, in per-request subfolders,
# so concurrent users (e.g. judges trying it at the same time) don't
# collide or overwrite each other's files.
BASE_DIR = tempfile.mkdtemp(prefix="ytdl_")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/formats", methods=["POST"])
def formats():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return jsonify({"error": f"Couldn't read that URL ({e})"}), 400

    heights = sorted(
        {f["height"] for f in info.get("formats", []) if f.get("height")},
        reverse=True,
    )
    options = [f"{h}p" for h in heights]
    options.append("Audio only (MP3)")

    return jsonify({"title": info.get("title", "video"), "options": options})


@app.route("/download", methods=["POST"])
def download():
    url = request.form.get("url", "").strip()
    quality = request.form.get("quality", "")
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    job_id = str(uuid.uuid4())
    job_dir = os.path.join(BASE_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    options = {
        "noplaylist": True,
        "outtmpl": os.path.join(job_dir, "%(title)s.%(ext)s"),
        "quiet": True,
    }

    if quality.startswith("Audio"):
        options.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        height = quality.replace("p", "")
        options["format"] = (
            f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"
        )
        options["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if quality.startswith("Audio"):
                filename = os.path.splitext(filename)[0] + ".mp3"
            elif not filename.endswith(".mp4"):
                filename = os.path.splitext(filename)[0] + ".mp4"
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 400

    if not os.path.exists(filename):
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": "File not found after download"}), 500

    response = send_file(filename, as_attachment=True)

    # Clean up the temp folder once the response has been fully sent.
    @response.call_on_close
    def _cleanup():
        shutil.rmtree(job_dir, ignore_errors=True)

    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
