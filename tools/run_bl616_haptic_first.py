from pathlib import Path

patch_path = Path("tools/apply_bl616_haptic_first.py")
source = patch_path.read_text()
source = source.replace(
    'if s.count(reset_pat) != 2:\n    raise SystemExit(f"reset pattern expected 2 matches, found {s.count(reset_pat)}")',
    'if s.count(reset_pat) != 3:\n    raise SystemExit(f"reset pattern expected 3 matches, found {s.count(reset_pat)}")'
)
exec(compile(source, str(patch_path), "exec"), {"__name__": "__main__"})

# The generic reset transform also touches audio_init, whose explicit init
# transform already added the flag. Collapse that one harmless duplicate.
p = Path("src/audio.c")
s = p.read_text()
dup = '''    audio_batch_count = 0;\n    speaker_pipeline_primed = false;\n    audio_batch_speaker = false;\n    audio_batch_headset = false;\n    audio_batch_channels = 1;\n    speaker_pipeline_primed = false;'''
clean = '''    audio_batch_count = 0;\n    audio_batch_speaker = false;\n    audio_batch_headset = false;\n    audio_batch_channels = 1;\n    speaker_pipeline_primed = false;'''
if dup not in s:
    raise SystemExit("audio_init duplicate-collapse anchor not found")
s = s.replace(dup, clean, 1)
p.write_text(s)
print("BL616 haptics-first transform completed with corrected reset handling")
