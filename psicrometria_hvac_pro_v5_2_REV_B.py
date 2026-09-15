# -*- coding: utf-8 -*-
"""
PSICROMETRIA HVAC PRO V5.4
Modulo PROCESOS dinamico:
- El usuario selecciona UN proceso.
- Los puntos editables cambian segun el proceso.
- Solo se dibuja el proceso seleccionado.
- Carta ajustada por altitud.
- Propiedades psicrometricas y tabla de resultados.
"""
import math
import tkinter as tk
from tkinter import ttk, messagebox

GRAINS=7000.0

def p_atm_pa(alt_m):
    h=float(alt_m)
    return 101325.0*(1.0-2.25577e-5*h)**5.2559

def pws_pa_f(tf):
    tc=(float(tf)-32)*5/9; T=tc+273.15
    if tc>=0:
        ln=(-5.8002206e3/T+1.3914993-4.8640239e-2*T+4.1764768e-5*T*T
            -1.4452093e-8*T**3+6.5459673*math.log(T))
    else:
        ln=(-5.6745359e3/T+6.3925247-9.677843e-3*T+6.2215701e-7*T*T
            +2.0747825e-9*T**3-9.484024e-13*T**4+4.1635019*math.log(T))
    return math.exp(ln)

def w_from_t_rh(tf,rh,alt_m):
    p=p_atm_pa(alt_m); pw=max(0,min(1,float(rh)/100))*pws_pa_f(tf)
    return .621945*pw/max(p-pw,1)

def rh_from_t_w(tf,w,alt_m):
    p=p_atm_pa(alt_m); pw=p*w/(.621945+w)
    return 100*pw/pws_pa_f(tf)

def h_ip(tf,w): return .240*tf+w*(1061+.444*tf)

def v_ip(tf,w,alt_m):
    psia=p_atm_pa(alt_m)/6894.757293
    return .370486*(tf+459.67)*(1+1.607858*w)/psia

def state(tf,rh,alt_m):
    w=w_from_t_rh(tf,rh,alt_m)
    return {"T":float(tf),"RH":float(rh),"W":w,"Wgr":w*GRAINS,
            "h":h_ip(float(tf),w),"v":v_ip(float(tf),w,alt_m)}

PROCESSES={
 "Enfriamiento 100% aire exterior (OA → S)":(
   "OA - Aire exterior","S - Salida serpentín",
   (95,60),(55,95),
   "El aire exterior se enfría y deshumidifica directamente hasta la salida del serpentín."),
 "Enfriamiento y deshumidificación (M → S)":(
   "M - Mezcla / Entrada","S - Salida serpentín",
   (85,70),(55,95),
   "Enfriamiento con reducción de temperatura y razón de humedad."),
 "Enfriamiento sensible (1 → 2)":(
   "1 - Entrada","2 - Salida",(85,45),(65,65),
   "Enfriamiento sensible. Para un proceso ideal, W permanece constante."),
 "Calentamiento sensible (1 → 2)":(
   "1 - Entrada","2 - Salida",(55,60),(85,28),
   "Calentamiento sensible. Para un proceso ideal, W permanece constante."),
 "Humidificación adiabática (1 → 2)":(
   "1 - Entrada","2 - Salida",(90,20),(70,55),
   "Humidificación con enfriamiento evaporativo aproximadamente a entalpía constante."),
 "Calentamiento + humidificación (1 → 2)":(
   "1 - Entrada","2 - Salida",(55,30),(80,50),
   "Proceso combinado con aumento de temperatura y contenido de humedad."),
 "Deshumidificación (1 → 2)":(
   "1 - Entrada","2 - Salida",(80,70),(55,90),
   "Proceso con remoción de humedad; puede incluir enfriamiento y condensación."),
 "Mezcla de dos corrientes (A + B → M)":(
   "A - Corriente 1","B - Corriente 2",(95,55),(75,50),
   "Se muestran las dos condiciones seleccionadas para análisis de mezcla.")
}

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PSICROMETRIA HVAC PRO V5.4 — Carta Psicrométrica Profesional")
        self.geometry("1550x920"); self.minsize(1200,720)
        self.alt=tk.StringVar(value="1000")
        self.proc=tk.StringVar(value=list(PROCESSES)[0])
        self.t1=tk.StringVar(); self.rh1=tk.StringVar()
        self.t2=tk.StringVar(); self.rh2=tk.StringVar()
        self.s1=self.s2=None
        self.build(); self.change_process()

    def build(self):
        style=ttk.Style(self)
        try: style.theme_use("clam")
        except: pass
        style.configure(".", font=("Segoe UI",9), background="#f5faff")
        style.configure("TFrame", background="#f5faff")
        style.configure("TLabel", background="#f5faff", foreground="#17365d")
        style.configure("TLabelframe", background="#f5faff", bordercolor="#9cc9f5", relief="solid")
        style.configure("TLabelframe.Label", background="#e7f3ff", foreground="#0756b3", font=("Segoe UI",10,"bold"))
        style.configure("TButton", padding=7)
        style.configure("Blue.TButton", background="#0878e8", foreground="white", font=("Segoe UI",10,"bold"))
        style.map("Blue.TButton", background=[("active","#0867c8")])
        style.configure("TCombobox", padding=4)
        self.configure(bg="#eef7ff")

        top=ttk.Frame(self,padding=8); top.pack(fill="x")
        ttk.Label(top,text="❄  PSICROMETRIA HVAC PRO V5.4",foreground="#064da8",font=("Segoe UI",19,"bold")).pack(side="left")
        ttk.Label(top,text="Altitud:").pack(side="left",padx=(35,4))
        ttk.Entry(top,textvariable=self.alt,width=8).pack(side="left")
        ttk.Label(top,text="m").pack(side="left")
        ttk.Button(top,text="Actualizar altitud",command=self.calculate).pack(side="left",padx=6)

        nav=ttk.Frame(self,padding=(8,2)); nav.pack(fill="x")
        for txt in ["Estados","Procesos","Mezcla","Serpentín / Bypass","Zona (RSHF)","Torres","Herramientas","Reportes"]:
            b=ttk.Button(nav,text=txt)
            b.pack(side="left",padx=1)
        ttk.Separator(self,orient="horizontal").pack(fill="x",padx=8,pady=(2,4))

        body=ttk.Panedwindow(self,orient="horizontal"); body.pack(fill="both",expand=True,padx=8,pady=4)
        left=ttk.Frame(body,padding=6); center=ttk.Frame(body,padding=4)
        body.add(left,weight=0); body.add(center,weight=1)

        f=ttk.LabelFrame(left,text="1. SELECCIONE EL PROCESO",padding=8); f.pack(fill="x")
        cb=ttk.Combobox(f,textvariable=self.proc,values=list(PROCESSES),state="readonly",width=43)
        cb.pack(fill="x"); cb.bind("<<ComboboxSelected>>",lambda e:self.change_process())
        self.desc=ttk.Label(f,wraplength=355,justify="left"); self.desc.pack(fill="x",pady=8)

        d=ttk.LabelFrame(left,text="2. MODIFIQUE LOS PUNTOS DEL PROCESO",padding=8); d.pack(fill="x",pady=8)
        self.l1=ttk.Label(d,font=("Segoe UI",10,"bold")); self.l1.grid(row=0,column=0,columnspan=3,sticky="w",pady=4)
        ttk.Label(d,text="Temperatura").grid(row=1,column=0,sticky="w"); ttk.Entry(d,textvariable=self.t1,width=12).grid(row=1,column=1); ttk.Label(d,text="°F").grid(row=1,column=2)
        ttk.Label(d,text="Humedad relativa").grid(row=2,column=0,sticky="w"); ttk.Entry(d,textvariable=self.rh1,width=12).grid(row=2,column=1); ttk.Label(d,text="%").grid(row=2,column=2)
        self.l2=ttk.Label(d,font=("Segoe UI",10,"bold")); self.l2.grid(row=3,column=0,columnspan=3,sticky="w",pady=(12,4))
        ttk.Label(d,text="Temperatura").grid(row=4,column=0,sticky="w"); ttk.Entry(d,textvariable=self.t2,width=12).grid(row=4,column=1); ttk.Label(d,text="°F").grid(row=4,column=2)
        ttk.Label(d,text="Humedad relativa").grid(row=5,column=0,sticky="w"); ttk.Entry(d,textvariable=self.rh2,width=12).grid(row=5,column=1); ttk.Label(d,text="%").grid(row=5,column=2)
        ttk.Button(d,text="CALCULAR Y ACTUALIZAR CARTA",command=self.calculate,style="Blue.TButton").grid(row=6,column=0,columnspan=3,sticky="ew",pady=12)

        o=ttk.LabelFrame(left,text="3. VISUALIZACIÓN",padding=8); o.pack(fill="x")
        self.showvals=tk.BooleanVar(value=True)
        ttk.Checkbutton(o,text="Mostrar valores de los puntos",variable=self.showvals,command=self.draw).pack(anchor="w")
        ttk.Label(o,text="Solo se traza el proceso actualmente seleccionado.",wraplength=350).pack(anchor="w",pady=5)

        self.canvas=tk.Canvas(center,bg="white",highlightbackground="#9ab",highlightthickness=1)
        self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<Configure>",lambda e:self.draw())

        bottom=ttk.Frame(center); bottom.pack(fill="x",pady=4)
        self.tree=ttk.Treeview(bottom,columns=("p1","p2","dif"),show="headings",height=6)
        self.tree.heading("p1",text="Punto inicial"); self.tree.heading("p2",text="Punto final"); self.tree.heading("dif",text="Diferencia")
        self.tree.pack(side="left",fill="x",expand=True)
        self.info=tk.Text(bottom,width=38,height=7); self.info.pack(side="left",padx=(5,0))

    def change_process(self):
        a,b,x,y,desc=PROCESSES[self.proc.get()]
        self.l1.config(text=a); self.l2.config(text=b); self.desc.config(text=desc)
        self.t1.set(str(x[0])); self.rh1.set(str(x[1])); self.t2.set(str(y[0])); self.rh2.set(str(y[1]))
        self.calculate()

    def bounds(self): return 30,125,0,210
    def xy(self,T,W):
        t0,t1,w0,w1=self.bounds(); Wd=max(self.canvas.winfo_width(),650); Hd=max(self.canvas.winfo_height(),500)
        ml,mr,mt,mb=55,45,45,55
        return ml+(T-t0)/(t1-t0)*(Wd-ml-mr), mt+(w1-W)/(w1-w0)*(Hd-mt-mb)

    def calculate(self):
        try:
            alt=float(self.alt.get()); self.s1=state(float(self.t1.get()),float(self.rh1.get()),alt); self.s2=state(float(self.t2.get()),float(self.rh2.get()),alt)
            self.update_results(); self.draw()
        except Exception as e: messagebox.showerror("Datos del proceso",str(e))

    def update_results(self):
        for x in self.tree.get_children(): self.tree.delete(x)
        for label,key,fmt in [("Temperatura °F","T",".2f"),("HR %","RH",".2f"),("W lbw/lbda","W",".5f"),("Entalpía Btu/lbda","h",".2f"),("Volumen ft³/lbda","v",".2f")]:
            a=self.s1[key]; b=self.s2[key]
            self.tree.insert("", "end", values=(f"{label}: {a:{fmt}}",f"{b:{fmt}}",f"{b-a:{fmt}}"))
        p=p_atm_pa(float(self.alt.get()))
        self.info.delete("1.0","end")
        self.info.insert("end",f"CONDICIONES ATMOSFÉRICAS\nAltitud = {float(self.alt.get()):,.0f} m\nPresión = {p/1000:.2f} kPa\nPresión = {p/3386.389:.2f} inHg\n\n{PROCESSES[self.proc.get()][4]}")

    def draw(self):
        c=self.canvas; c.delete("all")
        if not self.s1 or not self.s2:return
        alt=float(self.alt.get()); Wd=max(c.winfo_width(),650); Hd=max(c.winfo_height(),500)
        c.create_text(70,18,text="CARTA PSICROMÉTRICA",anchor="w",fill="#064da8",font=("Segoe UI",16,"bold"))
        c.create_text(70,37,text=f"Presión ajustada: {p_atm_pa(alt)/1000:.2f} kPa   |   Altitud: {alt:,.0f} m",anchor="w",font=("Segoe UI",9,"bold"))
        # dry-bulb grid
        for T in range(30,126,5):
            x0,y0=self.xy(T,0); x1,y1=self.xy(T,210); c.create_line(x0,y0,x1,y1,fill="#ededed")
            if T%10==0:c.create_text(x0,Hd-27,text=str(T),anchor="n",font=("Segoe UI",8))
        for W in range(0,211,10):
            x0,y0=self.xy(30,W); x1,y1=self.xy(125,W); c.create_line(x0,y0,x1,y1,fill="#f0f0f0")
        # RH curves
        for rh in range(10,101,10):
            pts=[]
            for i in range(191):
                T=30+i*.5; W=w_from_t_rh(T,rh,alt)*GRAINS
                if 0<=W<=210: pts+=self.xy(T,W)
            if len(pts)>3:c.create_line(*pts,fill="#ff2d2d" if rh==100 else "#ff6767",width=2 if rh==100 else 1)
        # enthalpy lines
        for h in range(15,61,5):
            pts=[]
            for i in range(191):
                T=30+i*.5; w=(h-.240*T)/(1061+.444*T); W=w*GRAINS
                if w>=0 and W<=210 and W<=w_from_t_rh(T,100,alt)*GRAINS: pts+=self.xy(T,W)
            if len(pts)>3:c.create_line(*pts,fill="#16a05d",dash=(5,3))
        # selected process only
        x1,y1=self.xy(self.s1["T"],self.s1["Wgr"]); x2,y2=self.xy(self.s2["T"],self.s2["Wgr"])
        c.create_line(x1,y1,x2,y2,width=4,fill="#009bb5",arrow="last",arrowshape=(12,14,5))
        c.create_oval(x1-6,y1-6,x1+6,y1+6,fill="#16a05d"); c.create_oval(x2-6,y2-6,x2+6,y2+6,fill="#123fd1")
        a,b,*_=PROCESSES[self.proc.get()]
        c.create_text(x1+8,y1-8,text=a.split(" - ")[0],anchor="sw",font=("Segoe UI",10,"bold"))
        c.create_text(x2+8,y2+8,text=b.split(" - ")[0],anchor="nw",font=("Segoe UI",10,"bold"))
        if self.showvals.get():
            c.create_text(x1+8,y1+8,text=f"{self.s1['T']:.1f}°F | {self.s1['RH']:.0f}% | W={self.s1['W']:.4f}",anchor="nw",font=("Segoe UI",8))
            c.create_text(x2+8,y2-8,text=f"{self.s2['T']:.1f}°F | {self.s2['RH']:.0f}% | W={self.s2['W']:.4f}",anchor="sw",font=("Segoe UI",8))
        c.create_text(Wd/2,Hd-8,text="Temperatura de bulbo seco [°F]",font=("Segoe UI",9,"bold"))
        c.create_text(Wd-12,Hd/2,text="Razón de humedad [grains/lbda]",angle=90,font=("Segoe UI",9,"bold"))

if __name__=="__main__":
    App().mainloop()
