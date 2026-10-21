import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY", "")
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Fetch all free models
res = requests.get("https://openrouter.ai/api/v1/models")
models = res.json().get("data", [])
free_models = [m["id"] for m in models if ":free" in m["id"] or str(m.get("pricing", {}).get("prompt")) == "0"]

print(f"Found {len(free_models)} free models. Testing them...")

working_models = []

for model in free_models:
    print(f"Testing {model}...")
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Return the JSON `{\"status\": \"ok\"}`"}],
                "max_tokens": 50
            },
            timeout=10
        )
        data = resp.json()
        if "error" in data:
            print(f"  [ERROR] {data['error'].get('message')}")
        else:
            content = data["choices"][0]["message"]["content"]
            print(f"  [SUCCESS] {content.strip()}")
            working_models.append(model)
            # Break early if we find a good one
            if len(working_models) >= 3:
                break
    except Exception as e:
        print(f"  [EXCEPTION] {e}")
    time.sleep(1)

print("\n--- WORKING FREE MODELS ---")
for wm in working_models:
    print(wm)
