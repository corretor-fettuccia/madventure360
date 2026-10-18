#!/usr/bin/env python3
"""Madventure Stitch Studio - independent experimental dual-fisheye desktop converter."""
import os, sys, math, threading, queue, zipfile, traceback, subprocess, shutil, time
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import cv2
from PIL import Image, ImageTk

EXTS={'.jpg','.jpeg','.png','.webp','.tif','.tiff','.bmp'}
VIDEOS={'.mp4','.mov','.mkv','.avi','.mts','.m2ts','.webm'}
MEDIA=EXTS | VIDEOS

def is_supported_image(path):
    return Path(path).suffix.casefold() in EXTS

def file_dialog_filters():
    # On some Linux Tk builds, extension filters can be case-sensitive in practice.
    # Use "all files" in the picker and validate extensions in Python to avoid missed .JPG files.
    return [('Todos os arquivos', '*')]


def imread(path):
    raw=np.fromfile(str(path),np.uint8)
    image=cv2.imdecode(raw,cv2.IMREAD_COLOR)
    if image is None: raise ValueError('Imagem ilegível ou formato não suportado')
    return image

def imwrite(path,img):
    ext=Path(path).suffix.lower()
    ok, data=cv2.imencode(ext,img, [cv2.IMWRITE_JPEG_QUALITY,94] if ext in ('.jpg','.jpeg') else [cv2.IMWRITE_PNG_COMPRESSION,3])
    if not ok: raise ValueError('Falha ao gravar imagem')
    data.tofile(str(path))

def split_fisheyes(img,orientation):
    h,w=img.shape[:2]
    if orientation=='Horizontal':
        if w< h*1.2: raise ValueError('Imagem não parece conter duas lentes lado a lado')
        m=w//2
        return img[:,:m].copy(),img[:,m:].copy()
    if h<w*1.2: raise ValueError('Imagem não parece conter duas lentes empilhadas')
    m=h//2
    return img[:m,:].copy(),img[m:,:].copy()

def _smoothstep(edge0, edge1, x):
    t=np.clip((x-edge0)/max(edge1-edge0,1e-6),0,1)
    return t*t*(3-2*t)

def _edge_soft_mask(radius_norm, inner=0.90, outer=0.995):
    # 1.0 in the useful lens area, falling smoothly near the fisheye circle border.
    return 1.0 - _smoothstep(inner, outer, radius_norm)

def _match_exposure(front, back, overlap_mask):
    if np.count_nonzero(overlap_mask) < 500:
        return back
    f=front[overlap_mask].astype(np.float32)
    b=back[overlap_mask].astype(np.float32)
    mean_f=f.mean(axis=0); mean_b=b.mean(axis=0)
    std_f=f.std(axis=0)+1e-3; std_b=b.std(axis=0)+1e-3
    gain=np.clip(std_f/std_b,0.80,1.25)
    bias=np.clip(mean_f-(mean_b*gain),-20,20)
    corrected=np.clip(back.astype(np.float32)*gain+bias,0,255)
    return corrected.astype(np.uint8)

def render(img, width=4096, fov=195., yaw=0., pitch=0., roll=0., orientation='Horizontal', blend=12., ev_match=True):
    left,right=split_fisheyes(img,orientation)
    height=width//2
    yy,xx=np.mgrid[0:height,0:width].astype(np.float32)
    lon=(xx+.5)/width*(2*np.pi)-np.pi
    lat=np.pi/2-(yy+.5)/height*np.pi
    cl=np.cos(lat)
    vx=cl*np.cos(lon); vy=cl*np.sin(lon); vz=np.sin(lat)
    yaw=np.deg2rad(yaw); pitch=np.deg2rad(pitch); roll=np.deg2rad(roll)

    def project(lens, rear):
        x,y,z=vx,vy,vz
        if rear:
            x,y,z=-x,-y,z
            if yaw: x,y=x*np.cos(yaw)+y*np.sin(yaw),-x*np.sin(yaw)+y*np.cos(yaw)
            if pitch: x,z=x*np.cos(pitch)-z*np.sin(pitch),x*np.sin(pitch)+z*np.cos(pitch)
            if roll: y,z=y*np.cos(roll)-z*np.sin(roll),y*np.sin(roll)+z*np.cos(roll)
        theta=np.arccos(np.clip(x,-1,1))
        radius_norm=theta/np.deg2rad(fov/2)
        H,W=lens.shape[:2]; R=min(W,H)*.495
        sin_theta=np.maximum(np.sin(theta),1e-6)
        mx=W*.5+(y/sin_theta)*radius_norm*R
        my=H*.5-(z/sin_theta)*radius_norm*R
        valid=(radius_norm<=1) & (theta<=np.deg2rad(fov/2))
        sampled=cv2.remap(lens,mx.astype(np.float32),my.astype(np.float32),cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
        soft=(_edge_soft_mask(radius_norm) * valid.astype(np.float32)).astype(np.float32)
        return sampled, soft, radius_norm

    front,af,_=project(left,False)
    back,ab,_=project(right,True)

    overlap=(af>0.01) & (ab>0.01)
    if ev_match:
        back=_match_exposure(front, back, overlap)

    overlap_rad=np.deg2rad(max(0.4, float(blend)))
    t=np.clip((vx - (-np.sin(overlap_rad))) / max(2*np.sin(overlap_rad),1e-6), 0, 1)
    ang_weight=t*t*(3-2*t)

    wf=(ang_weight*af).astype(np.float32)
    wb=((1.0-ang_weight)*ab).astype(np.float32)

    # Blur the seam weights so the transition becomes less visible.
    blur_px=max(3, int(width/1024)*2+1)
    if blur_px % 2 == 0:
        blur_px += 1
    wf=cv2.GaussianBlur(wf,(blur_px,blur_px),0)
    wb=cv2.GaussianBlur(wb,(blur_px,blur_px),0)

    denom=wf+wb+1e-6
    result=((front.astype(np.float32)*wf[...,None]) + (back.astype(np.float32)*wb[...,None])) / denom[...,None]
    empty=(denom<=1e-4)
    result[empty]=0

    # Mild seam-only finishing blur to hide residual stitching transition without softening the whole panorama.
    seam_zone=((wf>0.05) & (wb>0.05)).astype(np.uint8)
    if np.count_nonzero(seam_zone) > 100:
        soft=cv2.GaussianBlur(result.astype(np.uint8),(0,0),sigmaX=1.0)
        seam_mix=(cv2.GaussianBlur(seam_zone.astype(np.float32),(0,0),sigmaX=max(0.8, blend/10.0))*0.35)[...,None]
        result=result*(1-seam_mix)+soft.astype(np.float32)*seam_mix

    return np.clip(result,0,255).astype(np.uint8)

def auto_calibrate(img,orientation='Horizontal', fov=195):
    thumb=cv2.resize(img, (min(img.shape[1],1500),max(2,int(img.shape[0]*min(img.shape[1],1500)/img.shape[1]))))
    scores=[]
    for angle in range(-8,9,1):
        panorama=render(thumb,1024,fov,yaw=angle,orientation=orientation,blend=4,ev_match=False)
        h,w=panorama.shape[:2]
        e1=np.mean(np.abs(panorama[:,w//4-3].astype(np.float32)-panorama[:,w//4+3].astype(np.float32)))
        e2=np.mean(np.abs(panorama[:,3*w//4-3].astype(np.float32)-panorama[:,3*w//4+3].astype(np.float32)))
        scores.append((e1+e2,angle))
    score,angle=min(scores)
    return float(angle), float(score)


def is_media(path):
    return Path(path).suffix.casefold() in MEDIA

def convert_video(src, dest, opts, out_width, quality, cancel, progress):
    if not shutil.which('ffmpeg'):
        raise RuntimeError('FFmpeg não instalado. Execute: sudo apt install ffmpeg')
    capture=cv2.VideoCapture(str(src))
    if not capture.isOpened():
        raise ValueError('Vídeo não pôde ser aberto pelo OpenCV')
    fps=float(capture.get(cv2.CAP_PROP_FPS))
    if not np.isfinite(fps) or fps<1 or fps>240: fps=30.0
    total=int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    codec_cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','bgr24',
               '-s',f'{out_width}x{out_width//2}','-r',f'{fps:.5f}','-i','pipe:0',
               '-i',str(src),'-map','0:v:0','-map','1:a?','-c:v','libx264','-preset','veryfast',
               '-crf',str(quality),'-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-shortest',
               '-movflags','+faststart',str(dest)]
    proc=subprocess.Popen(codec_cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    count=0
    try:
        while not cancel.is_set():
            ok,frame=capture.read()
            if not ok:break
            out=render(frame,width=out_width,**opts)
            try: proc.stdin.write(out.tobytes())
            except BrokenPipeError:break
            count+=1
            if count % 10==0: progress(count,total)
        proc.stdin.close()
        err=proc.stderr.read().decode(errors='replace')
        code=proc.wait()
        if cancel.is_set():
            dest.unlink(missing_ok=True)
            raise InterruptedError('Cancelado')
        if code!=0:
            dest.unlink(missing_ok=True)
            raise RuntimeError('FFmpeg: '+err[-550:])
        if count==0:raise RuntimeError('Não foram encontrados quadros válidos no vídeo')
        progress(count,total)
        return count
    finally:
        capture.release()
        if proc.poll() is None:
            proc.kill();proc.wait()

class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Madventure Stitch Studio — Linux v0.7')
        self.geometry('1340x840');self.minsize(1050,680)
        self.files=[];self.outputs=[];self.events=queue.Queue();self.busy=False
        self.cancel=threading.Event()
        self.output=tk.StringVar(value=str(Path.home()/'Imagens'/'Madventure360'))
        self.orientation=tk.StringVar(value='Horizontal');self.fov=tk.DoubleVar(value=195)
        self.width=tk.StringVar(value='4096');self.blend=tk.DoubleVar(value=14)
        self.vwidth=tk.StringVar(value='2048');self.quality=tk.StringVar(value='21')
        self.autocal=tk.BooleanVar(value=True);self.once=tk.BooleanVar(value=True);self.exposure=tk.BooleanVar(value=True)
        self.status=tk.StringVar(value='Pronto. Adicione fotos ou vídeos da câmera.')
        self.details=tk.StringVar(value='0 fotos   •   0 vídeos   •   0 concluídos')
        self.build();self.after(100,self.poll)

    def build(self):
        self.configure(bg='#eef2f7')
        sty=ttk.Style(self);sty.theme_use('clam')
        sty.configure('.',font=('DejaVu Sans',10))
        sty.configure('TFrame',background='#eef2f7')
        sty.configure('Pane.TFrame',background='white')
        sty.configure('TLabel',background='#eef2f7',foreground='#263449')
        sty.configure('Pane.TLabel',background='white',foreground='#263449')
        sty.configure('PaneTitle.TLabel',background='white',foreground='#162a44',font=('DejaVu Sans',12,'bold'))
        sty.configure('PaneHint.TLabel',background='white',foreground='#607185',font=('DejaVu Sans',9))
        sty.configure('TButton',padding=(11,9))
        sty.configure('Primary.TButton',background='#146de3',foreground='white',padding=(13,13),font=('DejaVu Sans',11,'bold'))
        sty.map('Primary.TButton',background=[('active','#0c55b8'),('disabled','#93b4df')])
        sty.configure('Danger.TButton',foreground='#a52d2d')
        sty.configure('Treeview',background='white',fieldbackground='white',rowheight=32,borderwidth=0)
        sty.configure('Treeview.Heading',background='#e8eff8',font=('DejaVu Sans',10,'bold'),padding=(5,9))
        sty.configure('TNotebook',background='white',borderwidth=0)
        sty.configure('TNotebook.Tab',padding=(15,10))
        sty.configure('TCheckbutton',background='white')
        sty.configure('Horizontal.TProgressbar',background='#146de3',troughcolor='#d7e2f0',thickness=10)
        top=tk.Frame(self,bg='#12233b',height=86);top.pack(fill='x');top.pack_propagate(False)
        title=tk.Frame(top,bg='#12233b');title.pack(side='left',padx=22,pady=14)
        tk.Label(title,text='MADVENTURE  /  STITCH STUDIO',bg='#12233b',fg='white',font=('DejaVu Sans',17,'bold')).pack(anchor='w')
        tk.Label(title,text='Conversão local de fotografias e vídeos dual-fisheye para 360°',bg='#12233b',fg='#adcae6',font=('DejaVu Sans',9)).pack(anchor='w',pady=(4,0))
        tk.Label(top,text='LINUX · v0.7',bg='#263d59',fg='#e2f0ff',padx=13,pady=7).pack(side='right',padx=24)

        tools=ttk.Frame(self,padding=(18,14,18,10));tools.pack(fill='x')
        self.import_btn=ttk.Button(tools,text='＋ Adicionar arquivos',command=self.add);self.import_btn.pack(side='left',padx=(0,8))
        ttk.Button(tools,text='▣ Adicionar pasta',command=self.add_dir).pack(side='left',padx=(0,8))
        ttk.Button(tools,text='Remover selecionados',command=self.remove_selected).pack(side='left',padx=(0,8))
        ttk.Button(tools,text='Limpar fila',command=self.clear).pack(side='left')
        ttk.Label(tools,textvariable=self.details).pack(side='right',padx=5)

        split=ttk.Panedwindow(self,orient='horizontal');split.pack(fill='both',expand=True,padx=18,pady=(0,10))
        left=ttk.Frame(split,style='Pane.TFrame',padding=16)
        right=ttk.Frame(split,style='Pane.TFrame',padding=16)
        split.add(left,weight=7);split.add(right,weight=4)
        left.rowconfigure(1,weight=1);left.columnconfigure(0,weight=1)
        ttk.Label(left,text='Fila de processamento',style='PaneTitle.TLabel').grid(row=0,column=0,sticky='w',pady=(0,12))
        area=ttk.Frame(left,style='Pane.TFrame');area.grid(row=1,column=0,sticky='nsew')
        area.rowconfigure(0,weight=1);area.columnconfigure(0,weight=1)
        self.tree=ttk.Treeview(area,columns=('tipo','nome','status'),show='headings',selectmode='extended')
        for col,caption in [('tipo','TIPO'),('nome','ARQUIVO'),('status','SITUAÇÃO')]:self.tree.heading(col,text=caption)
        self.tree.column('tipo',width=67,stretch=False);self.tree.column('nome',width=370,stretch=True);self.tree.column('status',width=150,stretch=False)
        self.tree.grid(row=0,column=0,sticky='nsew')
        scrollbar=ttk.Scrollbar(area,orient='vertical',command=self.tree.yview);scrollbar.grid(row=0,column=1,sticky='ns')
        self.tree.configure(yscrollcommand=scrollbar.set)
        ttk.Label(left,text='Extensões aceitas sem diferenciar maiúsculas: JPG, JPEG, PNG, TIFF, WEBP, BMP, MP4, MOV, MKV, AVI, MTS, M2TS e WEBM.',style='PaneHint.TLabel',wraplength=620).grid(row=2,column=0,sticky='w',pady=(14,0))

        right.columnconfigure(0,weight=1)
        ttk.Label(right,text='Configurações de conversão',style='PaneTitle.TLabel').grid(row=0,column=0,sticky='w',pady=(0,12))
        tabs=ttk.Notebook(right);tabs.grid(row=1,column=0,sticky='ew')
        common=ttk.Frame(tabs,style='Pane.TFrame',padding=12)
        images=ttk.Frame(tabs,style='Pane.TFrame',padding=12)
        videos=ttk.Frame(tabs,style='Pane.TFrame',padding=12)
        for frame,name in [(common,'Calibração'),(images,'Fotografias'),(videos,'Vídeos')]:tabs.add(frame,text=name);frame.columnconfigure(0,weight=1)
        def field(frame, label, var, choices=None):
            ttk.Label(frame,text=label,style='Pane.TLabel').pack(anchor='w',pady=(9,3))
            if choices:widget=ttk.Combobox(frame,textvariable=var,values=choices,state='readonly')
            else:widget=ttk.Entry(frame,textvariable=var)
            widget.pack(fill='x')
        field(common,'Posição das lentes',self.orientation,['Horizontal','Vertical'])
        field(common,'Campo de visão por lente (graus)',self.fov)
        field(common,'Suavização da emenda (graus)',self.blend)
        ttk.Checkbutton(common,text='Equalizar exposição entre lentes',variable=self.exposure).pack(anchor='w',pady=(15,4))
        ttk.Checkbutton(common,text='Autocalibrar fotografias (yaw)',variable=self.autocal).pack(anchor='w',pady=4)
        ttk.Checkbutton(common,text='Reutilizar calibração no lote',variable=self.once).pack(anchor='w',pady=4)
        ttk.Label(common,text='Vídeos usam os parâmetros do painel; a autocalibração por quadro ainda não é implementada.',style='PaneHint.TLabel',wraplength=345).pack(anchor='w',pady=(15,2))
        field(images,'Largura do panorama PNG',self.width,['2048','4096','6000','8192'])
        ttk.Label(images,text='Altura = metade da largura. Fotografias são exportadas como PNG sem perdas.',style='PaneHint.TLabel',wraplength=335).pack(anchor='w',pady=(15,5))
        field(videos,'Largura do vídeo 360°',self.vwidth,['1024','2048','3072','4096'])
        field(videos,'Qualidade MP4 / H.264 (CRF)',self.quality,['18','21','23','26','28'])
        ttk.Label(videos,text='FFmpeg obrigatório · Áudio original copiado para o vídeo final por recodificação AAC quando disponível. FPS original preservado quando detectável.',style='PaneHint.TLabel',wraplength=345).pack(anchor='w',pady=(15,4))
        ttk.Label(right,text='Destino dos arquivos',style='Pane.TLabel').grid(row=2,column=0,sticky='w',pady=(18,5))
        dest=ttk.Frame(right,style='Pane.TFrame');dest.grid(row=3,column=0,sticky='ew');dest.columnconfigure(0,weight=1)
        ttk.Entry(dest,textvariable=self.output).grid(row=0,column=0,sticky='ew',padx=(0,6))
        ttk.Button(dest,text='…',command=self.choose_out,width=3).grid(row=0,column=1)
        right.rowconfigure(4,weight=1)
        actions=ttk.Frame(right,style='Pane.TFrame');actions.grid(row=5,column=0,sticky='ew',pady=(16,0));actions.columnconfigure(0,weight=1)
        self.runbtn=ttk.Button(actions,text='▶  PROCESSAR FILA',style='Primary.TButton',command=self.start)
        self.runbtn.grid(row=0,column=0,sticky='ew',pady=(0,7))
        self.stopbtn=ttk.Button(actions,text='■  Cancelar após o quadro atual',command=self.stop,state='disabled')
        self.stopbtn.grid(row=1,column=0,sticky='ew',pady=(0,7))
        ttk.Button(actions,text='↓ Exportar resultados em ZIP',command=self.export_zip).grid(row=2,column=0,sticky='ew',pady=(0,7))
        ttk.Button(actions,text='Abrir destino',command=self.open_out).grid(row=3,column=0,sticky='ew')
        footer=ttk.Frame(self,padding=(18,2,18,14));footer.pack(fill='x')
        self.progress=ttk.Progressbar(footer,mode='determinate');self.progress.pack(fill='x',pady=(0,8))
        ttk.Label(footer,textvariable=self.status).pack(anchor='w')

    def recount(self):
        n=sum(Path(p).suffix.casefold() in EXTS for p in self.files)
        self.details.set(f'{n} fotos   •   {len(self.files)-n} vídeos   •   {len(self.outputs)} concluídos')
    def add_files(self,paths):
        added=0
        for p in paths:
            p=Path(p)
            if not p.is_file() or not is_media(p) or str(p) in self.files:continue
            self.files.append(str(p));i=str(len(self.files)-1)
            kind='VÍDEO' if p.suffix.casefold() in VIDEOS else 'FOTO'
            self.tree.insert('','end',iid=i,values=(kind,p.name,'Aguardando'));added+=1
        self.recount();self.status.set(f'{added} novo(s) arquivo(s). {len(self.files)} na fila.')
    def add(self): self.add_files(filedialog.askopenfilenames(title='Selecionar fotos e vídeos',filetypes=[('Todos os arquivos','*')]))
    def add_dir(self):
        p=filedialog.askdirectory(title='Importar diretório (incluindo subpastas)')
        if p:self.add_files(sorted(str(x) for x in Path(p).rglob('*') if x.is_file() and is_media(x)))
    def remove_selected(self):
        if self.busy:return
        selected=set(self.tree.selection())
        old=self.files[:];self.files=[];self.tree.delete(*self.tree.get_children())
        for i,f in enumerate(old):
            if str(i) not in selected:self.files.append(f)
        remaining=self.files[:];self.files=[];self.add_files(remaining)
    def clear(self):
        if self.busy:return
        self.files=[];self.outputs=[];self.tree.delete(*self.tree.get_children());self.progress['value']=0;self.recount();self.status.set('Fila limpa.')
    def choose_out(self):
        p=filedialog.askdirectory(title='Selecionar pasta de destino')
        if p:self.output.set(p)
    def start(self):
        if self.busy or not self.files:return
        try:
            w=int(self.width.get());vw=int(self.vwidth.get());fov=float(self.fov.get());blend=float(self.blend.get());crf=int(self.quality.get())
            if not 1024<=w<=8192 or not 1024<=vw<=4096 or vw%2 or not 180<=fov<=230 or not 0.1<=blend<=30 or not 0<=crf<=51:raise ValueError('Verifique resolução e parâmetros numéricos.')
            opts=dict(fov=fov,blend=blend,orientation=self.orientation.get(),ev_match=self.exposure.get())
        except Exception as e:messagebox.showerror('Parâmetros inválidos',str(e));return
        self.cancel.clear();self.busy=True;self.outputs=[];self.runbtn.configure(state='disabled');self.stopbtn.configure(state='normal')
        self.progress.configure(maximum=len(self.files),value=0)
        self.recount()
        threading.Thread(target=self.worker,args=(list(self.files),Path(self.output.get()),opts,w,vw,crf,self.autocal.get(),self.once.get()),daemon=True).start()
    def stop(self):
        if self.busy:self.cancel.set();self.status.set('Cancelamento solicitado…')
    def worker(self,files,folder,opts,w,vw,crf,auto,once):
        try:
            folder.mkdir(parents=True,exist_ok=True);yaw_cache=None
            for idx,f in enumerate(files):
                if self.cancel.is_set():break
                p=Path(f);video=p.suffix.casefold() in VIDEOS
                self.events.put(('status',idx,'Processando…'))
                dest=folder/(p.stem+('_360.mp4' if video else '_360.png'));n=2
                while dest.exists():dest=folder/(p.stem+f'_360_{n}'+dest.suffix);n+=1
                try:
                    if video:
                        self.events.put(('message','Convertendo vídeo '+p.name+' (pode demorar).'))
                        def tick(frame,total):
                            percent=f'{frame/total*100:.0f}%' if total>0 else f'{frame} quadros'
                            self.events.put(('status',idx,percent))
                        convert_video(p,dest,opts,vw,crf,self.cancel,tick)
                        yaw=0.0
                    else:
                        img=imread(p)
                        if auto and (yaw_cache is None or not once):
                            yaw,_=auto_calibrate(img,orientation=opts['orientation'],fov=opts['fov'])
                            if once:yaw_cache=yaw
                        else:yaw=yaw_cache or 0.0
                        imwrite(dest,render(img,width=w,yaw=yaw,**opts))
                    self.events.put(('ok',idx,str(dest),'MP4' if video else f'PNG ({yaw:+.0f}°)'))
                except InterruptedError:
                    self.events.put(('status',idx,'Cancelado'));break
                except Exception as e:
                    dest.unlink(missing_ok=True)
                    self.events.put(('error',idx,str(e)))
                self.events.put(('progress',idx+1))
        except Exception as e:self.events.put(('fatal',str(e)))
        finally:self.events.put(('done',))
    def poll(self):
        try:
            while True:
                ev=self.events.get_nowait();kind=ev[0]
                if kind=='status':self.tree.set(str(ev[1]),'status',ev[2])
                elif kind=='message':self.status.set(ev[1])
                elif kind=='ok':self.outputs.append(ev[2]);self.tree.set(str(ev[1]),'status',ev[3]);self.recount()
                elif kind=='error':self.tree.set(str(ev[1]),'status','Erro');self.status.set('Erro no arquivo '+str(ev[1]+1)+': '+ev[2])
                elif kind=='progress':self.progress['value']=ev[1]
                elif kind=='fatal':messagebox.showerror('Processamento',ev[1])
                elif kind=='done':
                    self.busy=False;self.runbtn.configure(state='normal');self.stopbtn.configure(state='disabled')
                    self.status.set(f'Finalizado: {len(self.outputs)}/{len(self.files)} arquivos. '+('Lote interrompido.' if self.cancel.is_set() else ''))
        except queue.Empty:pass
        self.after(100,self.poll)
    def export_zip(self):
        if self.busy:messagebox.showinfo('Aguarde','Conclua a conversão antes de criar o ZIP.');return
        if not self.outputs:messagebox.showinfo('Resultados','Nenhum resultado disponível.');return
        name=filedialog.asksaveasfilename(defaultextension='.zip',initialfile='Madventure360_lote.zip',filetypes=[('ZIP','*.zip')])
        if not name:return
        with zipfile.ZipFile(name,'w',zipfile.ZIP_STORED) as z:
            for f in self.outputs:
                if Path(f).exists():z.write(f,arcname=Path(f).name)
        self.status.set('ZIP salvo: '+name)
    def open_out(self):
        folder=Path(self.output.get());folder.mkdir(parents=True,exist_ok=True)
        subprocess.Popen(['xdg-open',str(folder)])

if __name__=='__main__':Studio().mainloop()
