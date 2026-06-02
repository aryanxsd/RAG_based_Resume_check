import json
import os
import subprocess
import textwrap
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT_DIR = Path(__file__).resolve().parents[2]
API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api")
DEMO_DIR = ROOT_DIR / "demo-video"
FRAME_DIR = DEMO_DIR / "frames"
VIDEO_PATH = DEMO_DIR / "candidate-screening-rag-demo.mp4"
TRANSCRIPT_PATH = DEMO_DIR / "demo-transcript.json"
RESUME_PATH = ROOT_DIR / "backend" / "data" / "sample_resume.txt"
ANSWER = (
    "I would define the task and metric first, split validation data carefully to avoid leakage, "
    "compare a baseline with a regularized model, inspect bias and variance through validation curves, "
    "and monitor precision, recall, drift, API session state, retrieved chunks, and persistence after deployment."
)


def request_json(path: str, method: str = "GET", data: bytes | None = None, headers: dict | None = None) -> dict:
    req = urllib.request.Request(f"{API_BASE}{path}", method=method, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"API is not reachable at {API_BASE}. Start the backend before creating the demo video.") from exc


def post_resume_session(role: str) -> dict:
    boundary = "codex-demo-boundary"
    resume_bytes = RESUME_PATH.read_bytes()
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"role\"\r\n\r\n{role}\r\n".encode("utf-8"),
        (
            f"--{boundary}\r\n"
            "Content-Disposition: form-data; name=\"resume\"; filename=\"sample_resume.txt\"\r\n"
            "Content-Type: text/plain\r\n\r\n"
        ).encode("utf-8"),
        resume_bytes,
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    body = b"".join(parts)
    return request_json(
        "/sessions",
        method="POST",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )


def post_answer(session_id: str, answer: str) -> dict:
    return request_json(
        f"/sessions/{session_id}/answers",
        method="POST",
        data=json.dumps({"answer": answer}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )


def run_demo_flow() -> dict:
    health = request_json("/health")
    roles = request_json("/roles")
    session = post_resume_session("ai_ml_engineer")
    answers = []
    for index in range(5):
        result = post_answer(session["session_id"], f"{ANSWER} Demo response {index + 1}.")
        answers.append(result)
        if result["status"] == "completed":
            break
    transcript = {"health": health, "roles": roles, "session": session, "answers": answers}
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPT_PATH.write_text(json.dumps(transcript, indent=2), encoding="utf-8")
    return transcript


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def draw_wrapped(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], width: int, fill: str, size: int = 34, bold: bool = False, spacing: int = 8) -> int:
    selected = font(size, bold)
    chars_per_line = max(24, int(width / (size * 0.54)))
    y = xy[1]
    for paragraph in text.split("\n"):
        lines = textwrap.wrap(paragraph, width=chars_per_line) or [""]
        for line in lines:
            draw.text((xy[0], y), line, font=selected, fill=fill)
            y += size + spacing
        y += spacing
    return y


def frame(title: str, subtitle: str, bullets: list[str], filename: str, accent: str = "#146c66") -> None:
    image = Image.new("RGB", (1280, 720), "#f6f8fb")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1280, 108), fill="#17324d")
    draw.rectangle((0, 108, 1280, 116), fill=accent)
    draw.text((54, 32), "Role-Based Candidate Screening RAG", font=font(28, True), fill="#ffffff")
    draw.text((54, 142), title, font=font(44, True), fill="#1e2329")
    draw_wrapped(draw, subtitle, (58, 202), 1120, "#4d5d6d", size=25)

    y = 292
    for bullet in bullets:
        draw.rounded_rectangle((58, y, 1222, y + 72), radius=8, fill="#ffffff", outline="#d9e0e8", width=2)
        draw.ellipse((82, y + 25, 100, y + 43), fill=accent)
        draw_wrapped(draw, bullet, (120, y + 17), 1050, "#26323d", size=24, bold=False, spacing=4)
        y += 88
        if y > 650:
            break

    image.save(FRAME_DIR / filename)


def make_frames(transcript: dict) -> None:
    FRAME_DIR.mkdir(parents=True, exist_ok=True)
    for old in FRAME_DIR.glob("*.png"):
        old.unlink()

    session = transcript["session"]
    first_question = session["current_question"]
    last_answer = transcript["answers"][-1]
    summary = last_answer["summary"]

    frame(
        "Complete Assignment Flow",
        "The repository contains a FastAPI backend, React frontend, SQLite persistence, and a traceable RAG pipeline.",
        [
            "Resume upload and role selection are handled by the React UI.",
            "FastAPI parses resumes, manages sessions, retrieves knowledge chunks, generates questions, and stores answers.",
            "SQLite stores both interview records and vector-search knowledge chunks.",
        ],
        "frame_001.png",
    )
    frame(
        "Knowledge Base and RAG",
        "The ingestion script loads role-specific seed text and the provided assignment book links when reachable.",
        [
            f"Health check: {transcript['health']['knowledge_chunks']} knowledge chunks available.",
            "Chunking preserves context; hashed local embeddings make the system runnable without API keys.",
            "Question traces store retrieval query, chunk IDs, source titles, keywords, and candidate signals.",
        ],
        "frame_002.png",
        "#b77a2a",
    )
    frame(
        "Resume Processing",
        "The sample resume was uploaded through the same /api/sessions endpoint used by the frontend.",
        [
            "Detected skills: " + ", ".join(session["extracted_skills"][:10]),
            "Detected domains: " + ", ".join(session["domains"]),
            "Topics selected: " + ", ".join(session["topics"][:8]),
        ],
        "frame_003.png",
    )
    frame(
        "Generated First Question",
        "The first question is influenced by the selected AI/ML role, the resume, and retrieved textbook context.",
        [
            first_question["question"],
            "Sources: " + ", ".join(first_question["generation_trace"]["source_titles"]),
            "Difficulty: " + first_question["difficulty"],
        ],
        "frame_004.png",
        "#6a4fb3",
    )
    frame(
        "Interactive Interview",
        "Five answers were submitted, persisted, scored, and used to adapt follow-up questions.",
        [
            f"Turn 1 score: {transcript['answers'][0]['answer_score']['score']}%",
            "Next question: " + transcript["answers"][0]["next_question"]["question"],
            "Answer feedback: " + transcript["answers"][0]["answer_score"]["feedback"],
        ],
        "frame_005.png",
        "#146c66",
    )
    frame(
        "Final Structured Summary",
        "The backend returns a final report after the configured question limit is reached.",
        [
            f"Overall score: {summary['overall_score']}% ({summary['readiness_band']})",
            "Recommendation: " + summary["recommendation"],
            "Traceability: " + summary["traceability_note"],
        ],
        "frame_006.png",
        "#8a3f2b",
    )
    frame(
        "Submission Ready",
        "This demo video, transcript, README, source code, and setup instructions are inside the new project folder.",
        [
            "Frontend URL: http://127.0.0.1:5173",
            "Backend docs: http://127.0.0.1:8000/docs",
            "Demo transcript: demo-video/demo-transcript.json",
        ],
        "frame_007.png",
    )


def ffmpeg_path() -> str:
    package_path = ROOT_DIR / "frontend" / "node_modules" / "ffmpeg-static" / "ffmpeg"
    if package_path.exists():
        return str(package_path)
    package_exe = ROOT_DIR / "frontend" / "node_modules" / "ffmpeg-static" / "ffmpeg.exe"
    if package_exe.exists():
        return str(package_exe)
    raise RuntimeError("ffmpeg-static binary not found. Run npm install in frontend.")


def encode_video() -> None:
    cmd = [
        ffmpeg_path(),
        "-y",
        "-framerate",
        "0.25",
        "-i",
        str(FRAME_DIR / "frame_%03d.png"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(VIDEO_PATH),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    transcript = run_demo_flow()
    make_frames(transcript)
    encode_video()
    print(VIDEO_PATH)


if __name__ == "__main__":
    main()
