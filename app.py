import os
import re
import time
import json
import subprocess
import urllib.parse
import urllib.request
import threading
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify, render_template, Response, send_from_directory
from dotenv import load_dotenv

try:
    from twilio.rest import Client
    from twilio.twiml.voice_response import VoiceResponse
except Exception as ex:
    Client = None
    VoiceResponse = None
    print(f"[Twilio Package Warning] {ex}")

load_dotenv()

# Environment Detection
IS_RENDER = bool(os.getenv("RENDER") or os.getenv("RENDER_EXTERNAL_HOSTNAME"))
IS_VERCEL = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
IS_CLOUD_PROD = IS_RENDER or IS_VERCEL or (os.name != "nt")

# Client Initializations
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

gemini = None
if GEMINI_API_KEY:
    try:
        from google import genai
        gemini = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as ex:
        print(f"[Gemini Init Warning] {ex}")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

twilio = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and Client:
    try:
        twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except Exception as ex:
        print(f"[Twilio Init Warning] {ex}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR,
)


@app.after_request
def add_security_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, ngrok-skip-browser-warning, Bypass-Tunnel-Remainder"
    response.headers["ngrok-skip-browser-warning"] = "true"
    response.headers["Bypass-Tunnel-Remainder"] = "true"
    return response


@app.route("/api/<path:path>", methods=["OPTIONS"])
def handle_options_preflight(path):
    response = Response("", status=200)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, ngrok-skip-browser-warning, Bypass-Tunnel-Remainder"
    return response





# =========================
# VOICE CATALOG & CONFIG
# =========================

VOICE_CATALOG: List[Dict[str, str]] = [
    # English Voices
    {
        "id": "Google.en-IN-Wavenet-D",
        "name": "Priya (Wavenet Neural Female - India)",
        "accent": "Indian English",
        "gender": "Female",
        "sample_text": "Namaste! I am Priya. I deliver warm, polite, and respectful customer feedback calls.",
    },
    {
        "id": "Google.en-IN-Wavenet-B",
        "name": "Rohan (Wavenet Neural Male - India)",
        "accent": "Indian English",
        "gender": "Male",
        "sample_text": "Hello! I am Rohan. I bring a clear, polite, and professional Indian male voice persona.",
    },
    
    # Marwari + Rajasthani + Hindi Voice Models (Twilio & Web Supported)
    {
        "id": "Google.hi-IN-Wavenet-B",
        "name": "Ratan Singh (Neural Male - Marwari, Rajasthani & Hindi)",
        "accent": "Rajasthani & Marwari Hindi",
        "gender": "Male",
        "sample_text": "राम राम सा! खम्मा घणी। मैं रतन सिंह, बीसीटी फ़ाइबरनेट से बात कर रहा हूँ।",
    },
    {
        "id": "Google.hi-IN-Wavenet-A",
        "name": "Gauri (Neural Female - Marwari, Rajasthani & Hindi)",
        "accent": "Rajasthani & Marwari Hindi",
        "gender": "Female",
        "sample_text": "खम्मा घणी! राम राम सा। मैं गौरी हूँ, बीसीटी फ़ाइबरनेट सेवा फ़ीडबैक के लिए कॉलिंग।",
    },
    {
        "id": "Polly.Aditi",
        "name": "Aditi / Sarvam (Indic Voice - Marwari + Rajasthani)",
        "accent": "Marwari + Rajasthani Dialect",
        "gender": "Female",
        "sample_text": "राम राम सा! खम्मा घणी हुकूम, बीसीटी फ़ाइबरनेट इंटरनेट सेवा री जानकारी दीजो।",
    },
]

SETTINGS_FILE = os.path.join(BASE_DIR, "settings_store.json")

DEFAULT_SETTINGS: Dict[str, Any] = {
    "active_voice": "Google.hi-IN-Wavenet-B",
    "speaking_rate": 1.0,
    "language": "hi-IN",
    "greeting_template": "Hello {customer_name}! Thank you for choosing BCT Fibernet. We are calling to collect your valuable service feedback.",
    "twilio_phone": "+919057262630",
    "max_call_duration": 3,
    "auto_retry": True,
    "max_retries": 2,
    "call_delay_seconds": 10,
    "instant_alerts": True,
    "alert_phone": "+919057262630",
    "alert_email": "vikas@example.com",
    "admin_username": "VIKAS",
    "admin_password": "7014",
    "poll_interval_ms": 2500,
    "theme": "light"
}

APP_SETTINGS: Dict[str, Any] = dict(DEFAULT_SETTINGS)

def load_settings_from_disk():
    global APP_SETTINGS, ACTIVE_VOICE
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    APP_SETTINGS.update(data)
                    if "active_voice" in APP_SETTINGS:
                        ACTIVE_VOICE = APP_SETTINGS["active_voice"]
        except Exception as ex:
            print(f"[Settings Load Error] {ex}")

def save_settings_to_disk():
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(APP_SETTINGS, f, indent=2, ensure_ascii=False)
    except Exception as ex:
        print(f"[Settings Save Error] {ex}")

load_settings_from_disk()

ACTIVE_VOICE = APP_SETTINGS.get("active_voice", "Google.hi-IN-Wavenet-B")


def get_active_agent_info() -> Dict[str, Any]:
    """Retrieves active voice catalog record and agent name."""
    global ACTIVE_VOICE
    v_info = next((v for v in VOICE_CATALOG if v["id"] == ACTIVE_VOICE), VOICE_CATALOG[0])
    return {
        "voice_id": ACTIVE_VOICE,
        "agent_name": v_info["name"].split(" ")[0],
        "info": v_info,
    }


def get_active_voice() -> str:
    """Returns active voice identifier string."""
    return ACTIVE_VOICE


def get_active_agent_name() -> str:
    """Returns active agent display name."""
    return get_active_agent_info()["agent_name"]


# =========================
# DYNAMIC TUNNEL MANAGEMENT
# =========================


active_tunnel_url = ""


def is_public_host(url: str) -> bool:
    """Returns True if URL is a valid public domain (excluding localhost, private IPs, and broken tunnel landing hosts)."""
    if not url:
        return False
    clean = url.replace("http://", "").replace("https://", "").strip()
    clean_host = clean.split(":")[0]
    if clean_host in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or clean_host.endswith(".local"):
        return False
    if clean_host.startswith("192.168.") or clean_host.startswith("10."):
        return False
    if clean_host.startswith("172."):
        parts = clean_host.split(".")
        if len(parts) >= 2 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31:
            return False
    if any(b in clean_host for b in ["loca.lt", "lhr.life", "serveo.net"]):
        return False
    return True


def get_twilio_voice(voice_id: str) -> str:
    """Safely maps voice identifier string to a valid Twilio <Say voice="..."> attribute value."""
    if not voice_id:
        return "Google.hi-IN-Wavenet-B"
        
    valid_twilio_voices = {
        "Google.hi-IN-Wavenet-A",
        "Google.hi-IN-Wavenet-B",
        "Google.hi-IN-Wavenet-C",
        "Google.hi-IN-Wavenet-D",
        "Google.en-IN-Wavenet-A",
        "Google.en-IN-Wavenet-B",
        "Google.en-IN-Wavenet-C",
        "Google.en-IN-Wavenet-D",
        "Polly.Aditi",
        "Polly.Kajal",
        "alice",
        "man",
        "woman"
    }
    if voice_id in valid_twilio_voices:
        return voice_id

    # Fallback mapping for custom voice strings to guaranteed valid Twilio voices
    if "Neural2-A" in voice_id or "Male" in voice_id:
        return "Google.hi-IN-Wavenet-B"
    if "Neural2-D" in voice_id or "Female" in voice_id or "Bulbul" in voice_id or "Sarvam" in voice_id:
        return "Google.hi-IN-Wavenet-A"
    if "hi-IN" in voice_id:
        return "Google.hi-IN-Wavenet-B"

    return "Google.hi-IN-Wavenet-B"


def get_base_url() -> str:
    """Returns live public HTTPS URL from request headers, cloud env, active tunnel, or BASE_URL."""
    global active_tunnel_url
    try:
        if request and request.host:
            req_host = request.headers.get("X-Forwarded-Host") or request.host
            req_host = req_host.split(",")[0].strip().rstrip("/")
            if is_public_host(req_host):
                if not req_host.startswith("http"):
                    live_url = f"https://{req_host}"
                else:
                    live_url = req_host.replace("http://", "https://")
                active_tunnel_url = live_url
                return live_url
    except Exception:
        pass

    r_host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if r_host:
        r_host = r_host.rstrip("/")
        if not r_host.startswith("http"):
            return f"https://{r_host}"
        return r_host.replace("http://", "https://")

    v_url = os.getenv("VERCEL_URL")
    if v_url:
        v_url = v_url.rstrip("/")
        if not v_url.startswith("http"):
            return f"https://{v_url}"
        return v_url.replace("http://", "https://")

    if active_tunnel_url and is_public_host(active_tunnel_url):
        clean_tunnel = active_tunnel_url.rstrip("/")
        return clean_tunnel.replace("http://", "https://")

    tunnel = ensure_tunnel()
    if tunnel and is_public_host(tunnel):
        clean_tunnel = tunnel.rstrip("/")
        return clean_tunnel.replace("http://", "https://")

    base_env = os.getenv("BASE_URL", "").strip().rstrip("/")
    if base_env and is_public_host(base_env):
        return base_env.replace("http://", "https://")

    return "http://127.0.0.1:5000"


def update_env_base_url(live_url: str) -> None:
    """Auto-updates BASE_URL key in environment without triggering file reloader loops."""
    if not live_url:
        return
    global active_tunnel_url
    active_tunnel_url = live_url
    os.environ["BASE_URL"] = live_url
    print(f"[Auto-Env] Dynamic BASE_URL set in memory to {live_url}")


def kill_zombie_cloudflared() -> None:
    """Terminates lingering cloudflared processes on Windows."""
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "cloudflared.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


def _drain_process_stdout(proc: subprocess.Popen) -> None:
    """Reads stdout continuously in background to prevent buffer fill deadlock."""
    try:
        while proc.poll() is None and proc.stdout:
            line = proc.stdout.readline()
            if not line:
                break
    except Exception:
        pass





import ssl

def verify_tunnel_url(url: str) -> bool:
    """Verifies that a public tunnel URL actually routes HTTP requests to Flask app."""
    if not url or not is_public_host(url):
        return False
    clean_url = url.rstrip("/") + "/api/health"
    try:
        req = urllib.request.Request(
            clean_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "ngrok-skip-browser-warning": "true",
                "Bypass-Tunnel-Remainder": "true",
            },
        )
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=3, context=ctx) as resp:
            if resp.status == 200:
                body = resp.read().decode("utf-8")
                if '"status": "ok"' in body or '"status":"ok"' in body:
                    return True
    except Exception as ex:
        print(f"[Tunnel Verify Check for {url}] {ex}")
    return False


def start_local_cloudflare_tunnel() -> Optional[str]:
    """Launches local Cloudflare Free Tunnel via cloudflared.exe with robust health verification."""
    global active_tunnel_url
    if IS_CLOUD_PROD:
        return None

    cf_bin = os.path.join(os.path.dirname(__file__), "cloudflared.exe")
    if not os.path.exists(cf_bin):
        return None

    kill_zombie_cloudflared()
    time.sleep(1)

    try:
        proc = subprocess.Popen(
            [cf_bin, "tunnel", "--url", "http://127.0.0.1:5000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        start_t = time.time()
        found_url = None
        while time.time() - start_t < 20:
            line = proc.stdout.readline()
            if not line:
                break
            if any(err in line for err in ["429", "Too Many Requests", "error code: 1015"]):
                try:
                    proc.kill()
                except Exception:
                    pass
                return None
            if "trycloudflare.com" in line:
                match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if match:
                    found_url = match.group(0)
                    print(f"[Cloudflare Tunnel Found] {found_url}. Waiting for DNS & QUIC propagation...")
                    
                    # Drain process stdout in background to prevent buffer stall
                    threading.Thread(target=_drain_process_stdout, args=(proc,), daemon=True).start()

                    # Wait up to 12 seconds for Cloudflare edge propagation
                    verified = False
                    for attempt in range(1, 13):
                        time.sleep(1)
                        if verify_tunnel_url(found_url):
                            verified = True
                            print(f"[CLOUDFLARE TUNNEL READY & VERIFIED ON ATTEMPT {attempt}] {found_url}")
                            break

                    if verified:
                        active_tunnel_url = found_url
                        update_env_base_url(found_url)
                        return found_url
                    else:
                        print(f"[Cloudflare Tunnel Failed 12s Verification] {found_url}")
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        return None
    except Exception as err:
        print(f"[Auto-Tunnel Error] {err}")

    return None


def get_ngrok_tunnel_url() -> Optional[str]:
    """Queries running ngrok local inspection endpoint (http://127.0.0.1:4040/api/tunnels)."""
    try:
        req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tunnels = data.get("tunnels", [])
            for t in tunnels:
                pub = t.get("public_url", "")
                if pub and pub.startswith("https://") and "ngrok" in pub:
                    return pub.rstrip("/")
    except Exception:
        pass
    return None


def start_local_ngrok_tunnel() -> Optional[str]:
    """Launches ngrok HTTP tunnel fallback if cloudflared is rate-limited (429)."""
    existing = get_ngrok_tunnel_url()
    if existing:
        update_env_base_url(existing)
        return existing
    try:
        subprocess.Popen(
            ["ngrok", "http", "5000", "--log=stdout"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(8):
            time.sleep(1)
            url = get_ngrok_tunnel_url()
            if url:
                update_env_base_url(url)
                print(f"[NGROK FALLBACK TUNNEL READY] {url}")
                return url
    except Exception as e:
        print(f"[Ngrok Auto-Tunnel Exception] {e}")
    return None


def ensure_tunnel() -> str:
    """Master auto-tunnel initializer: Cloudflare -> Ngrok -> BASE_URL fallback."""
    global active_tunnel_url
    if IS_CLOUD_PROD:
        return os.getenv("BASE_URL", "")

    if active_tunnel_url and is_public_host(active_tunnel_url):
        return active_tunnel_url

    # Check if ngrok is already running
    ngrok_url = get_ngrok_tunnel_url()
    if ngrok_url:
        active_tunnel_url = ngrok_url
        update_env_base_url(ngrok_url)
        return ngrok_url

    # Try Cloudflare tunnel
    cf_url = start_local_cloudflare_tunnel()
    if cf_url:
        return cf_url

    # Cloudflare was rate-limited or failed -> launch Ngrok tunnel automatically
    ngrok_fallback = start_local_ngrok_tunnel()
    if ngrok_fallback:
        return ngrok_fallback

    fallback = os.getenv("BASE_URL", "").strip().rstrip("/")
    if fallback and is_public_host(fallback):
        active_tunnel_url = fallback
        return fallback

    return fallback


# Start tunnel asynchronously on local dev to prevent blocking Flask server boot
if not IS_CLOUD_PROD and (os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("FLASK_ENV") != "development"):
    threading.Thread(target=ensure_tunnel, daemon=True).start()



# =========================
# DATA STORAGE & HELPERS
# =========================



def get_initial_seed_data() -> List[Dict[str, Any]]:
    """Returns initial seed customer records."""
    return [
        {
            "id": "c101",
            "name": "Vikas Kumar",
            "phone": "+919057262630",
            "status": "completed",
            "duration": "02:35",
            "feedback": ["The service was wonderful! Quick delivery and friendly staff."],
            "rating": 5,
            "sentiment": "Positive",
            "transcript": [
                {"speaker": "ai", "text": "राम राम सा! मैं बीसीटी फ़ाइबरनेट से बोल रहा हूँ। आपकी इंटरनेट सेवा कैसी चल रही है? थोड़ा फीडबैक दीजिए।"},
                {"speaker": "customer", "text": "अच्छी चल रही है।"},
                {"speaker": "ai", "text": "अच्छा, ये सुनकर अच्छा लगा। 5 स्टार देने के लिए धन्यवाद।"}
            ],
            "created_at": "Aug 17, 2025 10:24 AM",
            "last_call": "Today"
        },
        {
            "id": "c102",
            "name": "Priya Mehta",
            "phone": "+918765432109",
            "status": "completed",
            "duration": "03:12",
            "feedback": ["Delivery was on time but packaging could be better."],
            "rating": 3,
            "sentiment": "Neutral",
            "transcript": [
                {"speaker": "ai", "text": "Hello Priya! How was your recent order delivery?"},
                {"speaker": "customer", "text": "Delivery was on time but packaging could be better."},
                {"speaker": "ai", "text": "Thank you for letting us know! We will improve our packaging."}
            ],
            "created_at": "Aug 17, 2025 09:58 AM",
            "last_call": "3 days ago"
        },
        {
            "id": "c103",
            "name": "Arjun Verma",
            "phone": "+917654321098",
            "status": "completed",
            "duration": "01:48",
            "feedback": ["The product stopped working after a few days. Need help."],
            "rating": 1,
            "sentiment": "Negative",
            "transcript": [
                {"speaker": "ai", "text": "Hello Arjun! Calling regarding your service ticket."},
                {"speaker": "customer", "text": "The product stopped working after a few days. Need help."},
                {"speaker": "ai", "text": "We sincerely apologize! Our technician will reach out immediately."}
            ],
            "created_at": "Aug 17, 2025 09:41 AM",
            "last_call": "5 days ago"
        },
        {
            "id": "c104",
            "name": "Neha Kapoor",
            "phone": "+916543210987",
            "status": "completed",
            "duration": "02:05",
            "feedback": ["Great experience overall. Will recommend to others!"],
            "rating": 5,
            "sentiment": "Positive",
            "transcript": [
                {"speaker": "ai", "text": "Hi Neha! Thank you for choosing our service. How did we do?"},
                {"speaker": "customer", "text": "Great experience overall. Will recommend to others!"},
                {"speaker": "ai", "text": "Awesome! Have a fantastic day!"}
            ],
            "created_at": "Aug 17, 2025 09:20 AM",
            "last_call": "1 week ago"
        },
        {
            "id": "c105",
            "name": "Manish Yadav",
            "phone": "+915432109876",
            "status": "completed",
            "duration": "02:22",
            "feedback": ["The app is good but it needs more payment options."],
            "rating": 3,
            "sentiment": "Neutral",
            "transcript": [
                {"speaker": "ai", "text": "Hello Manish! How is the app experience going?"},
                {"speaker": "customer", "text": "The app is good but it needs more payment options."},
                {"speaker": "ai", "text": "Got it! Adding more payment options soon."}
            ],
            "created_at": "Aug 17, 2025 08:55 AM",
            "last_call": "1 week ago"
        },
        {
            "id": "c106",
            "name": "Sneha Iyer",
            "phone": "+914321098765",
            "status": "completed",
            "duration": "03:01",
            "feedback": ["Support team was very helpful and resolved my issue quickly."],
            "rating": 5,
            "sentiment": "Positive",
            "transcript": [
                {"speaker": "ai", "text": "Hi Sneha! Calling to confirm if your support ticket was resolved?"},
                {"speaker": "customer", "text": "Support team was very helpful and resolved my issue quickly."},
                {"speaker": "ai", "text": "Glad to hear that! Goodbye."}
            ],
            "created_at": "Aug 17, 2025 08:30 AM",
            "last_call": "2 weeks ago"
        }
    ]


DB_FILE_PATH = os.path.join("/tmp" if IS_CLOUD_PROD else os.path.dirname(__file__), "customers_store.json")


def load_customers_from_disk() -> List[Dict[str, Any]]:
    """Loads customer dataset from JSON storage file or seed fallback."""
    if os.path.exists(DB_FILE_PATH):
        try:
            with open(DB_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception as e:
            print(f"[Storage Load Error] {e}")
    return get_initial_seed_data()


def save_customers_to_disk() -> None:
    """Saves active customer dataset to JSON storage file."""
    try:
        with open(DB_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(customers, f, indent=2)
    except Exception as e:
        print(f"[Storage Save Error] {e}")


customers: List[Dict[str, Any]] = load_customers_from_disk()


def normalize_phone_number(phone: Any) -> str:
    """Normalizes phone numbers to standard E.164 format (+91XXXXXXXXXX)."""
    if not phone:
        return ""
    cleaned = re.sub(r"[^\d+]", "", str(phone).strip())
    if not cleaned:
        return ""
    if cleaned.startswith("+"):
        return cleaned
    if cleaned.startswith("00"):
        return "+" + cleaned[2:]
    if cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = cleaned[1:]
    if len(cleaned) == 10:
        return f"+91{cleaned}"
    if len(cleaned) == 12 and cleaned.startswith("91"):
        return f"+{cleaned}"
    return f"+{cleaned}"


def find_customer(
    customer_id: Optional[str] = None, phone: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Searches customer records by ID or phone number."""
    if customer_id:
        c = next((item for item in customers if item["id"] == customer_id), None)
        if c:
            return c
    if phone:
        norm_phone = normalize_phone_number(phone)
        clean_target = re.sub(r"\D", "", str(phone))
        for item in customers:
            item_phone = item.get("phone", "")
            if item_phone == norm_phone:
                return item
            clean_item = re.sub(r"\D", "", str(item_phone))
            if clean_item and (clean_item.endswith(clean_target) or clean_target.endswith(clean_item)):
                return item
    return None


def generate_ai_response(customer_text: str, customer: Optional[Dict[str, Any]] = None) -> str:
    """Generates conversational AI response via Gemini API with smart fallback."""
    ai_text = ""
    lower = customer_text.lower()
    active_v = get_active_voice()
    agent_info = get_active_agent_info()
    agent_name = agent_info["agent_name"]
    is_rajasthani_hindi = any(k in active_v for k in ["hi-IN", "Neural2", "Sarvam", "Bulbul"]) or "Hindi" in agent_info.get("info", {}).get("accent", "")

    if gemini:
        try:
            if is_rajasthani_hindi:
                prompt = (
                    f"You are {agent_name} calling from BCT Fibernet for customer feedback.\n"
                    f'The customer said: "{customer_text}"\n\n'
                    "EXACT DIALOGUE SCRIPT & STYLE RULES:\n"
                    "1. Respond in respectful Hindi/Rajasthani tone starting with 'राम राम सा!' when appropriate.\n"
                    "2. If customer says service is good/fine: say 'अच्छा, ये सुनकर अच्छा लगा। इंटरनेट की स्पीड भी ठीक मिल रही है?' or ask for 1 to 5 star rating.\n"
                    "3. If customer has issues/problems: say 'अच्छा, समझ गया। आपको किस तरह की परेशानी आ रही है? थोड़ा बताइए।' or 'ठीक है, आपकी बात नोट कर लेते हैं।'\n"
                    "4. Useful follow-up questions to use when appropriate:\n"
                    "   - 'इंटरनेट की स्पीड ठीक चल रही है?'\n"
                    "   - 'कनेक्शन में कोई परेशानी तो नहीं आ रही?'\n"
                    "   - 'इंटरनेट बार-बार बंद तो नहीं हो रहा?'\n"
                    "5. Keep replies super concise (maximum 15 words).\n"
                    "6. Output ONLY plain text without markdown, quotes, or internal labels."
                )
            else:
                prompt = (
                    f"You are {agent_name} calling from BCT Fibernet regarding internet service feedback.\n"
                    f'The customer said: "{customer_text}"\n\n'
                    "Rules:\n"
                    "1. Acknowledge their feedback about BCT Fibernet internet service naturally.\n"
                    "2. If they haven't given a 1 to 5 star rating yet, ask for a star rating out of 5.\n"
                    "3. Keep your reply super concise (maximum 15 words).\n"
                    "4. Speak naturally without markdown or internal labels."
                )
            for model_candidate in [GEMINI_MODEL, "gemini-3.6-flash", "gemini-2.5-flash"]:
                try:
                    res = gemini.models.generate_content(model=model_candidate, contents=prompt)
                    if res and res.text:
                        ai_text = res.text.strip()
                        break
                except Exception as ex_m:
                    print(f"[Gemini Model Candidate '{model_candidate}' Error] {ex_m}")
        except Exception as ex:
            print(f"[Gemini API Exception] {ex}")

    if not ai_text:
        nums = re.findall(r"\b([1-5])\b", customer_text)
        rating_num = int(nums[0]) if nums else (customer.get("rating") if customer else None)
        bye_words = ["bye", "goodbye", "thank you", "thanks", "that's all", "done", "no", "that is all", "राम राम", "धन्यवाद", "कोनी"]

        if any(w in lower for w in bye_words):
            ai_text = "राम राम! आपका दिन अच्छा रहे। बीसीटी फ़ाइबरनेट को समय देने के लिए धन्यवाद।" if is_rajasthani_hindi else "Thank you so much for your valuable feedback! Have a wonderful day. Goodbye!"
        elif rating_num:
            if rating_num >= 4:
                ai_text = f"अच्छा, ये सुनकर अच्छा लगा। {rating_num} स्टार देने के लिए धन्यवाद।" if is_rajasthani_hindi else f"Thank you so much for giving us {rating_num} stars! We are delighted to hear your feedback."
            else:
                ai_text = f"ठीक है, आपकी बात नोट कर लेते हैं। {rating_num} स्टार रेटिंग के लिए धन्यवाद।" if is_rajasthani_hindi else f"Thank you for your {rating_num} star rating. We sincerely apologize for any inconvenience and will work to improve."
        elif any(w in lower for w in ["good", "great", "excellent", "awesome", "amazing", "wonderful", "nice", "happy", "बढ़िया", "सही", "चोखो", "ठीक", "अच्छा", "अच्छी"]):
            ai_text = "बहुत बढ़िया! आपकी प्रतिक्रिया के लिए धन्यवाद।" if is_rajasthani_hindi else "That is so wonderful to hear! Thank you for your feedback."
        elif any(w in lower for w in ["bad", "poor", "slow", "worst", "terrible", "issue", "delay", "not good", "खराब", "धीमी", "बंद"]):
            ai_text = "आपकी परेशानी हमने नोट कर ली है। हमारी टीम जल्द सुधार करेगी।" if is_rajasthani_hindi else "We have noted your concern and will work to improve our service immediately."
        else:
            ai_text = "आपकी प्रतिक्रिया के लिए बीसीटी फ़ाइबरनेट की ओर से बहुत-बहुत धन्यवाद!" if is_rajasthani_hindi else "Thank you for sharing your valuable feedback with BCT Fibernet!"

    return ai_text


# =========================
# WEB ROUTES & ENDPOINTS
# =========================



@app.route("/")
@app.route("/api/index")
@app.route("/api/index.py")
def index():
    """Serves main dashboard SPA."""
    return render_template("index.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    """Serves static assets explicitly from STATIC_DIR with proper Content-Type & CORS headers."""
    response = send_from_directory(STATIC_DIR, filename)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Cache-Control"] = "no-cache, must-revalidate"
    if filename.endswith(".css"):
        response.headers["Content-Type"] = "text/css; charset=utf-8"
    elif filename.endswith(".js"):
        response.headers["Content-Type"] = "text/javascript; charset=utf-8"
    return response


@app.route("/style.css")
@app.route("/app.js")
@app.route("/fluid_orb.png")
@app.route("/favicon.ico")
def serve_root_static():
    """Fallback handler for root-level static asset requests."""
    filename = request.path.lstrip("/")
    if filename == "favicon.ico":
        filename = "fluid_orb.png"
    response = send_from_directory(STATIC_DIR, filename)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Cache-Control"] = "no-cache, must-revalidate"
    if filename.endswith(".css"):
        response.headers["Content-Type"] = "text/css; charset=utf-8"
    elif filename.endswith(".js"):
        response.headers["Content-Type"] = "text/javascript; charset=utf-8"
    return response



@app.route("/api/health")
def health():
    """Returns application health and environment info."""
    env_name = "Render Production" if IS_RENDER else ("Vercel Production" if IS_VERCEL else "Local Development")
    return jsonify({
        "status": "ok",
        "engine": "Gemini 2.5 Flash + Twilio Voice",
        "active_voice": get_active_voice(),
        "environment": env_name,
        "base_url": get_base_url(),
    })


@app.route("/api/settings", methods=["GET", "POST"])
def manage_settings():
    """GET returns current settings; POST updates settings persistently."""
    global APP_SETTINGS, ACTIVE_VOICE
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        if not data:
            return jsonify({"success": False, "error": "Invalid request payload"}), 400

        # Update settings dictionary safely
        for key in DEFAULT_SETTINGS.keys():
            if key in data:
                APP_SETTINGS[key] = data[key]

        if "active_voice" in data:
            ACTIVE_VOICE = str(data["active_voice"])
            APP_SETTINGS["active_voice"] = ACTIVE_VOICE

        save_settings_to_disk()
        return jsonify({
            "success": True,
            "message": "Settings updated and saved successfully",
            "settings": APP_SETTINGS
        })

    return jsonify({
        "success": True,
        "settings": APP_SETTINGS
    })



@app.route("/api/voices", methods=["GET", "POST"])
@app.route("/api/voices/select", methods=["POST"])
def manage_voices():
    """Fetches catalog or updates active AI voice."""
    global ACTIVE_VOICE
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        voice_id = data.get("voice_id")
        found = next((v for v in VOICE_CATALOG if v["id"] == voice_id), None)
        if not found:
            return jsonify({"success": False, "error": f"Voice ID '{voice_id}' not found in catalog"}), 400
        ACTIVE_VOICE = voice_id
        return jsonify({"success": True, "active_voice": ACTIVE_VOICE, "voice_info": found})

    return jsonify({"success": True, "active_voice": ACTIVE_VOICE, "voices": VOICE_CATALOG})



@app.route("/api/demo-audio", methods=["GET"])
def stream_voice_demo():
    """Streams sample audio voice preview."""
    voice_id = request.args.get("voice_id") or get_active_voice()
    v_info = next((v for v in VOICE_CATALOG if v["id"] == voice_id), VOICE_CATALOG[0])
    text = v_info.get("sample_text", "Hello! I am your AI Voice Assistant.")
    
    is_hindi_rajasthani = ("hi-IN" in voice_id) or ("Sarvam" in voice_id) or ("Hindi" in v_info.get("accent", "")) or ("Rajasthani" in v_info.get("accent", "")) or ("Marwari" in v_info.get("accent", ""))
    lang = "hi" if is_hindi_rajasthani else ("en-uk" if "GB" in voice_id else "en")

    tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl={lang}&client=tw-ob&q={urllib.parse.quote(text)}"
    try:
        req = urllib.request.Request(tts_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return Response(resp.read(), mimetype="audio/mpeg")
    except Exception as e:
        print(f"[Demo Audio Stream Error] {e}")
        return jsonify({"error": "Failed to stream audio"}), 500



@app.route("/api/customers", methods=["GET", "POST"])
def handle_customers():
    """Lists all customers or creates a new customer task."""
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        name = str(data.get("name", "")).strip()
        raw_phone = str(data.get("phone", "")).strip()

        if not name or not raw_phone:
            return jsonify({"success": False, "error": "Name and phone number are required"}), 400

        phone = normalize_phone_number(raw_phone)
        existing = find_customer(phone=phone)
        if existing:
            existing["name"] = name
            existing["status"] = "pending"
            save_customers_to_disk()
            return jsonify({"success": True, "customer": existing, "message": "Updated existing customer task"}), 200

        customer = {
            "id": f"c{int(time.time() % 100000)}",
            "name": name,
            "phone": phone,
            "status": "pending",
            "feedback": [],
            "rating": None,
            "sentiment": "Neutral",
            "transcript": [],
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
            "last_call": None,
        }
        customers.append(customer)
        save_customers_to_disk()
        return jsonify({"success": True, "customer": customer}), 201

    customers = load_customers_from_disk()
    return jsonify(customers)



@app.route("/api/customers/<customer_id>", methods=["GET", "DELETE"])
def handle_customer_by_id(customer_id):
    """Retrieves or deletes a single customer record."""
    global customers
    c = find_customer(customer_id=customer_id)
    if not c:
        return jsonify({"success": False, "error": "Customer not found"}), 404

    if request.method == "DELETE":
        customers = [item for item in customers if item["id"] != customer_id]
        save_customers_to_disk()
        return jsonify({"success": True, "message": "Customer deleted successfully"})

    return jsonify({"success": True, "customer": c})



@app.route("/api/customers/<customer_id>/feedback", methods=["DELETE"])
def delete_customer_feedback(customer_id):
    """Clears feedback history for a specific customer."""
    c = find_customer(customer_id=customer_id)
    if not c:
        return jsonify({"success": False, "error": "Customer not found"}), 404
    c.update({"feedback": [], "rating": None, "sentiment": "Neutral", "transcript": []})
    if c.get("status") == "completed":
        c["status"] = "pending"
    save_customers_to_disk()
    return jsonify({"success": True, "message": "Customer feedback cleared successfully", "customer": c})


@app.route("/api/seed", methods=["POST"])
def reset_seed_data():
    """Resets customer store back to initial sample dataset."""
    global customers
    customers.clear()
    customers.extend([
        {
            "id": "c101",
            "name": "Sarah Jenkins",
            "phone": "+919057262630",
            "status": "completed",
            "feedback": ["The service was wonderful! Quick delivery and friendly staff.", "I would rate it 5 stars."],
            "rating": 5,
            "sentiment": "Positive",
            "transcript": [
                {"speaker": "ai", "text": "Hello! This is Sarah calling from Feedback Ops. How was your experience with our service?"},
                {"speaker": "customer", "text": "The service was wonderful! Quick delivery and friendly staff."},
                {"speaker": "ai", "text": "That is so great to hear! How many stars out of 5 would you give us?"},
                {"speaker": "customer", "text": "I would rate it 5 stars."},
                {"speaker": "ai", "text": "Thank you so much for your feedback! Have a lovely day. Goodbye."},
            ],
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
            "last_call": "Recent",
        },
        {
            "id": "c102",
            "name": "David Miller",
            "phone": "+19164356173",
            "status": "pending",
            "feedback": [],
            "rating": None,
            "sentiment": "Neutral",
            "transcript": [],
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
            "last_call": None,
        },
        {
            "id": "c103",
            "name": "Priya Sharma",
            "phone": "+919876543210",
            "status": "pending",
            "feedback": [],
            "rating": None,
            "sentiment": "Neutral",
            "transcript": [],
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
            "last_call": None,
        },
    ])
    save_customers_to_disk()
    return jsonify({"success": True, "message": "Sample data reset successfully", "customers": customers})



# =========================
# CALL CONTROL & TWILIO API
# =========================



@app.route("/api/customers/<customer_id>/call", methods=["POST"])
def call_customer_by_id(customer_id):
    """Triggers outbound call for a specific customer ID."""
    return trigger_outbound_call(customer_id=customer_id)


@app.route("/api/call", methods=["POST"])
def make_call():
    """Triggers outbound AI voice feedback call."""
    data = request.get_json(force=True, silent=True) or {}
    customer_id = data.get("customer_id")
    phone = data.get("phone")
    return trigger_outbound_call(customer_id=customer_id, phone=phone)


def simulate_live_call(customer_id: str) -> None:
    """Simulates realistic live call transcript progression over background thread."""
    c = find_customer(customer_id=customer_id)
    if not c:
        return

    agent_name = get_active_agent_name()
    is_marwari = is_marwari_accent_active()

    if is_marwari:
        greeting = f"राम राम सा! मैं बीसीटी फ़ाइबरनेट से {agent_name} बोल रहा हूँ। आपकी इंटरनेट सेवा कैसी चल रही है?"
        customer_reply = "स्पीड बढ़िया मिल रही है, बस कभी-कभार शाम को थोड़ी धीमी होती है।"
        ai_response = "अच्छा, समझ गया सा। आपकी बात नोट कर ली है, शाम को स्पीड की जांच करवाएंगे।"
    else:
        greeting = f"Hello {c['name']}! I am {agent_name} from BCT Fibernet, calling for quick feedback on your internet service. How is your experience?"
        customer_reply = "The internet speed is very good! I am really satisfied with the support team as well."
        ai_response = "That is so wonderful to hear! Thank you so much for giving us your valuable feedback. Have a great day!"

    # Step 1: Initial call connected & greeting
    c["status"] = "calling"
    c["last_call"] = time.strftime("%H:%M:%S")
    c["transcript"] = [{"speaker": "ai", "text": greeting}]
    c["sentiment"] = "Neutral"
    save_customers_to_disk()

    # Step 2: Customer speaks after 2.5 seconds
    time.sleep(2.5)
    c = find_customer(customer_id=customer_id)
    if c:
        c.setdefault("feedback", []).append(customer_reply)
        c.setdefault("transcript", []).append({"speaker": "customer", "text": customer_reply})
        c["sentiment"] = "Positive"
        c["rating"] = 5
        save_customers_to_disk()

    # Step 3: AI closing response after 2.5 seconds & completion
    time.sleep(2.5)
    c = find_customer(customer_id=customer_id)
    if c:
        c.setdefault("transcript", []).append({"speaker": "ai", "text": ai_response})
        c["status"] = "completed"
        save_customers_to_disk()


def trigger_outbound_call(customer_id=None, phone=None):
    """Unified handler to execute outbound Twilio call."""
    customer = find_customer(customer_id=customer_id, phone=phone)
    if customer_id and not customer:
        return jsonify({"success": False, "error": "Customer ID not found"}), 404

    raw_target = customer["phone"] if customer else phone
    target_phone = normalize_phone_number(raw_target)
    if not target_phone:
        return jsonify({"success": False, "error": "Phone number or valid customer_id is required"}), 400

    if customer:
        customer["phone"] = target_phone

    base = get_base_url()
    if twilio and not is_public_host(base):
        return jsonify({
            "success": False,
            "error": "No active public HTTPS tunnel connected. Cloudflare quick tunnel is currently rate-limited (429). Please set a valid public BASE_URL in .env (e.g. ngrok http 5000) or wait for Cloudflare cooldown."
        }), 400

    cid_param = f"?customer_id={customer['id']}" if customer else f"?phone={urllib.parse.quote(target_phone)}"
    voice_url = f"{base}/api/twilio/voice{cid_param}"
    status_url = f"{base}/api/twilio/status{cid_param}"

    print(f"[Initiate Call] Dialing {target_phone} via Voice URL: {voice_url}")

    if not twilio:
        if customer:
            customer["status"] = "calling"
            customer["last_call"] = time.strftime("%H:%M:%S")
            save_customers_to_disk()
            threading.Thread(target=simulate_live_call, args=(customer["id"],), daemon=True).start()
        return jsonify({
            "success": True,
            "simulated": True,
            "message": f"Twilio client not initialized with real SID/Token, simulated live call started for {target_phone}.",
        })

    try:
        call = twilio.calls.create(
            to=target_phone,
            from_=TWILIO_PHONE_NUMBER,
            url=voice_url,
            method="POST",
            status_callback=status_url,
            status_callback_method="POST",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
        )

        if customer:
            customer["status"] = "calling"
            customer["call_sid"] = call.sid
            customer["last_call"] = time.strftime("%H:%M:%S")

        return jsonify({
            "success": True,
            "call_id": call.sid,
            "status": call.status,
            "message": f"AI call initiated to {customer['name'] if customer else target_phone}",
        })
    except Exception as e:
        print(f"[Call Exception] {e}")
        if customer:
            customer["status"] = "failed"
        return jsonify({"success": False, "error": str(e)}), 500


def is_marwari_accent_active() -> bool:
    """Checks if the currently active voice is a Marwari / Rajasthani / Hindi accent voice."""
    v = get_active_voice()
    info = get_active_agent_info()
    accent = info.get("info", {}).get("accent", "")
    return any(k in v for k in ["hi-IN", "Neural2", "Sarvam", "Bulbul", "Aditi", "Kajal"]) or "Rajasthani" in accent or "Marwari" in accent or "Hindi" in accent


@app.route("/api/twilio/voice", methods=["POST", "GET"])
def twilio_voice():
    """Initial TwiML entry point when call connects."""
    try:
        customer_id = request.args.get("customer_id")
        phone = request.args.get("phone") or request.form.get("To") or request.form.get("From")
        customer = find_customer(customer_id=customer_id, phone=phone)

        if customer:
            customer["status"] = "calling"
            save_customers_to_disk()

        base = get_base_url()
        cid_param = f"?customer_id={customer['id']}" if customer else ""
        feedback_url = f"{base}/api/twilio/feedback{cid_param}"

        response = VoiceResponse()
        agent_name = get_active_agent_name()
        c_name = customer["name"] if customer else ""
        v = get_twilio_voice(get_active_voice())
        is_marwari = is_marwari_accent_active()
        stt_lang = "hi-IN" if is_marwari else "en-IN"

        if is_marwari:
            greeting_text = "राम राम सा! मैं बीसीटी फ़ाइबरनेट से बोल रहा हूँ। आपकी इंटरनेट सेवा कैसी चल रही है? थोड़ा फीडबैक दीजिए।"
            closing_text = "राम राम! आपका दिन अच्छा रहे। बीसीटी फ़ाइबरनेट को समय देने के लिए धन्यवाद।"
        else:
            greeting_text = (
                f"Hello {c_name}! I am {agent_name} from BCT Fibernet, calling for quick feedback on your internet service. "
                "How is your experience?"
            )
            closing_text = "Thank you for your feedback! Goodbye."

        if customer:
            customer["transcript"] = [{"speaker": "ai", "text": greeting_text}]
            save_customers_to_disk()

        gather = response.gather(
            input="speech",
            action=feedback_url,
            method="POST",
            speech_timeout="auto",
            language=stt_lang,
        )
        gather.say(greeting_text, voice=v)

        response.say(closing_text, voice=v)
        response.hangup()

        return Response(str(response), status=200, mimetype="text/xml")
    except Exception as ex:
        print(f"[Twilio Voice Exception] {ex}")
        err_resp = VoiceResponse()
        err_resp.say("Hello! Thank you for calling BCT Fibernet. Have a wonderful day!", voice="Google.en-IN-Wavenet-B")
        err_resp.hangup()
        return Response(str(err_resp), status=200, mimetype="text/xml")


@app.route("/api/twilio/feedback", methods=["POST", "GET"])
def twilio_feedback():
    """Processes customer speech result and renders conversational response."""
    try:
        customer_id = request.args.get("customer_id")
        called_phone = request.form.get("To") or request.form.get("From")
        customer_text = request.form.get("SpeechResult", "").strip()
        customer = find_customer(customer_id=customer_id, phone=called_phone)

        response = VoiceResponse()
        base = get_base_url()
        cid_param = f"?customer_id={customer['id']}" if customer else ""
        feedback_url = f"{base}/api/twilio/feedback{cid_param}"
        v = get_twilio_voice(get_active_voice())
        is_marwari = is_marwari_accent_active()
        stt_lang = "hi-IN" if is_marwari else "en-IN"

        if not customer_text:
            no_speech_text = "जी, आपकी आवाज़ थोड़ी साफ़ नहीं आ रही है। एक बार फिर से बताइए।" if is_marwari else "I didn't quite catch that. Could you please tell me about your experience?"
            gather = response.gather(
                input="speech",
                action=feedback_url,
                method="POST",
                speech_timeout="auto",
                language=stt_lang,
            )
            gather.say(no_speech_text, voice=v)
            return Response(str(response), status=200, mimetype="text/xml")

        if customer:
            customer.setdefault("feedback", []).append(customer_text)
            customer.setdefault("transcript", []).append({"speaker": "customer", "text": customer_text})

            if customer.get("rating") is None:
                nums = re.findall(r"\b([1-5])\b", customer_text)
                if nums:
                    customer["rating"] = int(nums[0])

            pos_words = ["good", "great", "excellent", "amazing", "wonderful", "awesome", "fast", "love", "nice", "5", "4", "बढ़िया", "सही", "चोखो", "बढिया", "ठीक"]
            neg_words = ["bad", "poor", "terrible", "horrible", "slow", "delay", "worst", "hate", "1", "2", "खराब", "धीमी", "बेकार", "परेशानी", "बंद"]
            lower = customer_text.lower()
            if any(w in lower for w in pos_words):
                customer["sentiment"] = "Positive"
            elif any(w in lower for w in neg_words):
                customer["sentiment"] = "Negative"
            else:
                customer["sentiment"] = "Neutral"

        ai_text = generate_ai_response(customer_text, customer)
        if customer:
            customer.setdefault("transcript", []).append({"speaker": "ai", "text": ai_text})

        bye_msg = "राम राम! आपका दिन अच्छा रहे। बीसीटी फ़ाइबरनेट को समय देने के लिए धन्यवाद।" if is_marwari else "Have a fantastic day! Goodbye."

        response.say(ai_text, voice=v)
        response.say(bye_msg, voice=v)
        response.hangup()

        if customer:
            customer["status"] = "completed"
            save_customers_to_disk()

        return Response(str(response), status=200, mimetype="text/xml")
    except Exception as ex:
        print(f"[Twilio Feedback Exception] {ex}")
        err_resp = VoiceResponse()
        err_resp.say("Thank you for your valuable feedback! Have a great day.", voice="Google.en-IN-Wavenet-B")
        err_resp.hangup()
        return Response(str(err_resp), status=200, mimetype="text/xml")


@app.route("/api/twilio/status", methods=["POST"])
def twilio_status():
    """Webhook for Twilio call state transitions."""
    customer_id = request.args.get("customer_id")
    call_status = request.form.get("CallStatus", "")
    phone = request.form.get("To", "") or request.form.get("From", "")

    customer = find_customer(customer_id=customer_id, phone=phone)
    if customer:
        if call_status == "completed":
            customer["status"] = "completed"
        elif call_status in ("failed", "busy", "no-answer", "canceled"):
            customer["status"] = "failed"
        elif call_status in ("initiated", "ringing", "in-progress"):
            customer["status"] = "calling"
        save_customers_to_disk()

    return Response("OK", status=200)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
