# Whisplay Bitcoin Market Dashboard

An MFruit OS app: a crypto market dashboard for the PiSugar Whisplay HAT
(Raspberry Pi Zero 2 W / Orange Pi Zero 2W). Python 3.9+, Pillow, requests.

- **Follow `.claude/rules/mfruit-os-app.md`** (the MFruit OS app rules: one
  input controller, the same controls and look as MFruit OS, lifecycle).
- Input: `mfruit_sdk.input.InputController` → `DashboardApp.handle_action`
  (`app/main.py`). The page's hold/Enter action is `Screen.select_label`.
- Chrome: `app/ui/frame.py` composes a page with MFruit OS's status bar,
  footer hints and toast. Pages draw only between `theme.CONTENT_TOP` and
  `theme.CONTENT_BOTTOM`.
- `mfruit_sdk/` is vendored from MFruit OS — never edit it here; change
  `~/MFruitOS/mfruitos/sdk` and run `~/MFruitOS/scripts/sdk-sync.sh .`.
- Tests: `python3 -m pytest -q` (no hardware). Previews:
  `MFRUIT_FONT_DIR=~/MFruitOS/assets/fonts python3 tools/preview.py --mock`.
- Keep the README's Controls section in step with `handle_action`.
