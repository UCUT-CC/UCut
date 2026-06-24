import os
import polib

locale_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "app", "template", "locale")

for root, dirs, files in os.walk(locale_dir):
    for f in files:
        if f.endswith(".po"):
            po_path = os.path.join(root, f)
            mo_path = po_path.replace(".po", ".mo")
            try:
                po = polib.pofile(po_path)
                po.save_as_mofile(mo_path)
                print(f"OK: {po_path}")
            except Exception as e:
                print(f"FAIL: {po_path}: {e}")
