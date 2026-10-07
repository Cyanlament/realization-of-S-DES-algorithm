"""Build a GIF showing single-pair and multiple-pair key searches."""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
captures = ROOT / "evidence/screenshots"
names = ["06_attack_before.png", "07_attack_single_pair.png",
         "08_attack_multiple_before.png", "09_attack_multiple_result.png"]
frames = [Image.open(captures / name).convert("RGB") for name in names]
frames[0].save(ROOT / "evidence/brute_force_demo.gif", save_all=True, append_images=frames[1:],
               duration=[1500, 3500, 1500, 4500], loop=0, optimize=False, disposal=2)
print("Saved evidence/brute_force_demo.gif")
