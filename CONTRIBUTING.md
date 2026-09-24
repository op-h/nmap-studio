# Contributing

Thanks for taking a look.

## Getting set up

```bash
sudo apt install nmap python3-pyqt6      # or your distro's equivalent
git clone https://github.com/op-h/nmap-studio
cd nmap-studio
./nmap-studio
```

## Before you open a pull request

```bash
python3 selftest.py
```

Everything must pass. If you touched the scan process, run `--scan` too — it
starts a real nmap and checks output comes back.

## The shape of the code

`docs/TECHNICAL.md` explains the architecture. The short version:

- **One option = one row** in `nmapgui/optionsdata.py`. The UI, the command
  builder and the command parser all read from it. Adding an nmap flag should
  not mean touching a widget.
- **Results come from the XML, progress comes from stdout.** Keep them
  independent — if one fails the other must still work.
- **Design values come from `nmapgui/design.py`.** No hard-coded padding,
  radius or font size in a widget.
- **Icons are drawn, not imported.** Add a branch to `nmapgui/icons.py` and
  check it at 15px — thin strokes vanish at that size.

## Style

Plain Python, type hints where they help, comments that say *why* rather than
*what*. Match the file you are editing.
