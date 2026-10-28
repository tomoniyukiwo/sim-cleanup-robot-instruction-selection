"""Re-time one-frame-per-control-step recordings without rerunning inference."""
import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import shutil
import subprocess

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input',type=Path);ap.add_argument('output',type=Path)
    ap.add_argument('--control-fps',type=float,default=20)
    ap.add_argument('--speed',type=float,default=1.,help='1 = simulation speed; .5 = half speed')
    ap.add_argument('--output-fps',type=int,default=20)
    a=ap.parse_args()
    if any(not math.isfinite(x) or x<=0 for x in [a.control_fps,a.speed,a.output_fps]):ap.error('Rates must be positive')
    if not a.input.is_file():ap.error('Input not found')
    if a.output.exists():ap.error('Output exists: choose a new filename')
    for name in ['ffmpeg','ffprobe']:
        if not shutil.which(name):ap.error('Install ffmpeg first')
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=r_frame_rate,nb_read_frames,duration','-of','json',str(a.input)],text=True))['streams'][0]
    label=f'Playback {a.speed:g}x | control {a.control_fps:g} Hz'
    vf=f'drawbox=x=0:y=0:w=iw:h=30:color=black@0.75:t=fill,drawtext=text=\'{label}\':x=8:y=8:fontsize=13:fontcolor=white'
    a.output.parent.mkdir(parents=True,exist_ok=True)
    # Input -r deliberately ignores erroneous container timestamps; preserve all frames.
    subprocess.run(['ffmpeg','-v','error','-n','-r',str(a.control_fps*a.speed),'-i',str(a.input),
        '-an','-vf',vf,'-r',str(a.output_fps),'-fps_mode','cfr','-c:v','libx264','-crf','18',
        '-pix_fmt','yuv420p','-movflags','+faststart',str(a.output)],check=True)
    print(json.dumps({'source_fps':str(probe['r_frame_rate']),'source_frames':probe.get('nb_read_frames'),
        'source_duration':probe.get('duration'),'control_fps':a.control_fps,'playback_speed':a.speed,
        'output_fps':a.output_fps,'output':str(a.output)},indent=2))

if __name__=='__main__':main()
