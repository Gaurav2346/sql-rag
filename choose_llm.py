"""
Interactive provider picker.

Run this once to choose which LLM the whole project uses. It writes your
choice to llm_choice.json, which every run reads. No code editing.

    python choose_llm.py            # interactive menu
    python choose_llm.py nvidia     # set directly, no menu
    python choose_llm.py --show     # just print the current choice
"""

import json
import os
import sys

CHOICE_FILE = "llm_choice.json"

# name -> (env var needed, default model, human label)
PROVIDERS = {
    "nvidia": ("NVIDIA_API_KEY", "nvidia/nemotron-3-ultra-550b-a55b", "NVIDIA Nemotron"),
    "gemini": ("GEMINI_API_KEY", "gemini-3.6-flash","Google Gemini Flash"),
    "openai": ("OPENAI_API_KEY", "gpt-4o-mini","OpenAI GPT-4o-mini"),
    "deepseek": ("DEEPSEEK_API_KEY", "deepseek-v4-flash", "DeepSeek Chat"),
    "groq": ("GROQ_API_KEY", "llama-3.3-70b-versatile","Groq Llama 3.3 70B"),
    "ollama": ("", "qwen2.5-coder:7b","Local Ollama (no key needed)"),
    "openrouter": ("OPENROUTER_API_KEY", "openai/gpt-5.4-mini","OpenRouter - GPT-5.4 Mini"),
}


def load_env():
    """Read .env so we can show which keys are present."""
    keys = {}
    if os.path.exists(".env"):
        for line in open(".env"):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                keys[k.strip()] = v.strip()
    return keys


def save_choice(name):
    env_var, model, label = PROVIDERS[name]
    with open(CHOICE_FILE, "w") as f:
        json.dump({"provider": name, "model": model}, f, indent=2)
    print(f"\n  Selected: {label}")
    print(f"  Provider: {name}")
    print(f"  Model:    {model}")

    if env_var:
        keys = load_env()
        if env_var in keys and keys[env_var]:
            print(f"  Key:      {env_var} found in .env")
        else:
            print(f"\n  WARNING: {env_var} is NOT in your .env file.")
            print(f"  Add this line to .env:")
            print(f"      {env_var}=your-key-here")
    print(f"\n  Saved to {CHOICE_FILE}. All runs now use this provider.")


def show_current():
    if os.path.exists(CHOICE_FILE):
        c = json.load(open(CHOICE_FILE))
        print(f"Current: {c['provider']}  ({c['model']})")
    else:
        print("No choice saved yet -- run: python choose_llm.py")


def menu():
    keys = load_env()
    print("\n  Choose an LLM provider:\n")
    names = list(PROVIDERS.keys())
    for i, name in enumerate(names, 1):
        env_var, model, label = PROVIDERS[name]
        if not env_var:
            status = "no key needed"
        elif env_var in keys and keys[env_var]:
            status = "key ready"
        else:
            status = "key missing"
        print(f"    {i}. {label:28} [{status}]   {name}")
    print()
    raw = input("  Enter number (or name): ").strip().lower()
    if raw in PROVIDERS:
        return raw
    if raw.isdigit() and 1 <= int(raw) <= len(names):
        return names[int(raw) - 1]
    print("  Invalid choice.")
    sys.exit(1)


def main():
    if "--show" in sys.argv:
        show_current()
        return

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args and args[0] in PROVIDERS:
        save_choice(args[0])
        return
    if args:
        print(f"Unknown provider '{args[0]}'. Options: {', '.join(PROVIDERS)}")
        sys.exit(1)

    save_choice(menu())


if __name__ == "__main__":
    main()