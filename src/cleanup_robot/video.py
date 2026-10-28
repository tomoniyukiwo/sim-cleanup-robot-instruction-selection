"""Side-by-side cameras; simulation-time video, not wall-clock playback."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import numpy as np
import math

class Recorder:
    def __init__(self,path,fps,control_hz,canonical,speed=1.0):
        if not math.isfinite(speed) or speed<=0:raise ValueError("Playback speed must be positive")
        self.speed=speed
        import imageio.v2 as imageio
        self.writer=imageio.get_writer(str(path),fps=fps,codec='libx264',macro_block_size=16)
        self.fps=fps;self.control_hz=control_hz;self.written=0;self.canonical=canonical;self.last=None
    def __call__(self,obs,step,attempt,status):
        # 256-pixel camera images are enlarged for visibility, not extra resolution.
        im=Image.new('RGB',(1024,640),(17,24,39))
        for i,key in enumerate(['image','image2']):
            rgb=np.asarray(obs['pixels'][key])[::-1,::-1].copy()
            im.paste(Image.fromarray(rgb).resize((512,512)),(i*512,128))
        draw=ImageDraw.Draw(im)
        draw.text((16,12),f'CLEANUP ROBOT | attempt={attempt} | step={step} | {status}',fill='white')
        words=self.canonical.split();lines=['']
        for word in words:
            if len(lines[-1])+len(word)>115:lines.append('')
            lines[-1]+=word+' '
        for i,line in enumerate(lines[:3]):draw.text((16,35+16*i),line,fill='white')
        draw.text((16,94),f'Playback {self.speed:g}x simulation ({self.control_hz:g} Hz) | local VLA | goal checked by LIBERO',fill='white')
        target=int(step/self.control_hz/self.speed*self.fps)+1
        while self.written<target:self.writer.append_data(np.array(im));self.written+=1
        self.last=im
    def finish(self,success):
        if self.last is not None:
            im=self.last.copy();d=ImageDraw.Draw(im);d.rectangle((0,0,1024,30),fill=(17,24,39))
            d.text((16,10),'GOAL SATISFIED' if success else 'GOAL NOT REACHED',fill='white')
            for _ in range(self.fps*2):self.writer.append_data(np.array(im))
    def close(self):self.writer.close()
