# -*- coding: utf-8 -*-
"""
PSICROMETRIA HVAC PRO V6.2 INTERACTIVA
Carta interactiva: crear, mover y editar puntos; aplicar procesos entre cualquier par.
Unidades IP en carta. Presion corregida automaticamente por altitud.
"""
import math, tkinter as tk
from tkinter import ttk, messagebox

GRAINS=7000.0

def p_atm_pa(alt_m):
    return 101325.0*(1.0-2.25577e-5*float(alt_m))**5.2559

def pws_pa_f(tf):
    tc=(float(tf)-32.0)*5/9; T=tc+273.15
    if tc>=0:
        ln=(-5.8002206e3/T+1.3914993-4.8640239e-2*T+4.1764768e-5*T*T
            -1.4452093e-8*T**3+6.5459673*math.log(T))
    else:
        ln=(-5.6745359e3/T+6.3925247-9.677843e-3*T+6.2215701e-7*T*T
            +2.0747825e-9*T**3-9.484024e-13*T**4+4.1635019*math.log(T))
    return math.exp(ln)

def w_from_t_rh(tf,rh,alt):
    p=p_atm_pa(alt); pw=max(0,min(1,float(rh)/100))*pws_pa_f(tf)
    return .621945*pw/max(p-pw,1)

def rh_from_t_w(tf,w,alt):
    p=p_atm_pa(alt); pw=p*w/(.621945+w)
    return 100*pw/pws_pa_f(tf)

def h_ip(tf,w): return .240*tf+w*(1061+.444*tf)
def v_ip(tf,w,alt):
    psia=p_atm_pa(alt)/6894.757293
    return .370486*(tf+459.67)*(1+1.607858*w)/psia

def dewpoint(tf,w,alt):
    p=p_atm_pa(alt); pw=p*w/(.621945+w); lo=-40.; hi=float(tf)
    for _ in range(70):
        m=(lo+hi)/2
        if pws_pa_f(m)<pw: lo=m
        else: hi=m
    return (lo+hi)/2

def state_trh(tf,rh,alt):
    w=w_from_t_rh(tf,rh,alt)
    return {"T":float(tf),"RH":float(rh),"W":w,"Wgr":w*GRAINS,
            "h":h_ip(float(tf),w),"v":v_ip(float(tf),w,alt),
            "Tdp":dewpoint(float(tf),w,alt)}

PROCESSES=[
 "Línea libre / proceso personalizado",
 "Enfriamiento sensible",
 "Calentamiento sensible",
 "Enfriamiento y deshumidificación",
 "Calentamiento y humidificación",
 "Humidificación adiabática",
 "Deshumidificación",
 "Enfriamiento 100% aire exterior",
 "Mezcla de dos corrientes"
]

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PSICROMETRIA HVAC PRO V6.2 — ADP + BYPASS INTERACTIVO")
        self.geometry("1580x930"); self.minsize(1200,720)
        self.alt=tk.StringVar(value="1000")
        self.name=tk.StringVar(value="P1")
        self.t=tk.StringVar(value="75")
        self.rh=tk.StringVar(value="50")
        self.pfrom=tk.StringVar(); self.pto=tk.StringVar()
        self.process=tk.StringVar(value=PROCESSES[0])
        self.zone_point=tk.StringVar()
        self.coil_in=tk.StringVar()
        self.coil_out=tk.StringVar()
        self.qs=tk.StringVar(value="80000")
        self.ql=tk.StringVar(value="20000")
        self.adp_result=None
        self.points={}; self.processes=[]; self.selected=None; self.drag=None
        self.build()
        self.add_point("OA",95,60); self.add_point("R",75,50); self.add_point("S",55,95)

    def build(self):
        st=ttk.Style(self)
        try: st.theme_use("clam")
        except: pass
        st.configure(".",font=("Segoe UI",9))
        st.configure("Card.TLabelframe",background="#f6fbff",bordercolor="#9cccf5")
        st.configure("Card.TLabelframe.Label",foreground="#0756b3",background="#e7f3ff",font=("Segoe UI",10,"bold"))
        st.configure("Blue.TButton",background="#0878e8",foreground="white",font=("Segoe UI",10,"bold"),padding=8)
        st.map("Blue.TButton",background=[("active","#0867c8")])
        self.configure(bg="#eef7ff")

        head=ttk.Frame(self,padding=8); head.pack(fill="x")
        ttk.Label(head,text="❄  PSICROMETRIA HVAC PRO V6.2",foreground="#064da8",font=("Segoe UI",19,"bold")).pack(side="left")
        ttk.Label(head,text="Altitud").pack(side="left",padx=(35,4))
        ttk.Entry(head,textvariable=self.alt,width=8).pack(side="left"); ttk.Label(head,text="m").pack(side="left")
        ttk.Button(head,text="Actualizar",command=self.recalc_all).pack(side="left",padx=5)
        self.press=ttk.Label(head,text=""); self.press.pack(side="left",padx=12)

        nav=ttk.Frame(self,padding=(8,2)); nav.pack(fill="x")
        for x in ["Estados","Procesos","Mezcla","Serpentín / Bypass","Zona (RSHF)","Herramientas","Reportes"]:
            ttk.Button(nav,text=x).pack(side="left",padx=1)

        pan=ttk.Panedwindow(self,orient="horizontal"); pan.pack(fill="both",expand=True,padx=8,pady=6)
        left=ttk.Frame(pan,padding=5); right=ttk.Frame(pan,padding=3)
        pan.add(left,weight=0); pan.add(right,weight=1)

        f=ttk.LabelFrame(left,text="1. CREAR / EDITAR PUNTO",style="Card.TLabelframe",padding=8); f.pack(fill="x")
        for row,(lab,var,unit) in enumerate([("Nombre",self.name,""),("T bulbo seco",self.t,"°F"),("HR",self.rh,"%")]):
            ttk.Label(f,text=lab).grid(row=row,column=0,sticky="w",pady=3)
            ttk.Entry(f,textvariable=var,width=16).grid(row=row,column=1,pady=3); ttk.Label(f,text=unit).grid(row=row,column=2,sticky="w")
        ttk.Button(f,text="Agregar punto",style="Blue.TButton",command=self.add_from_form).grid(row=3,column=0,columnspan=3,sticky="ew",pady=(8,3))
        ttk.Button(f,text="Actualizar seleccionado",command=self.update_selected).grid(row=4,column=0,columnspan=3,sticky="ew",pady=3)
        ttk.Button(f,text="Eliminar seleccionado",command=self.delete_selected).grid(row=5,column=0,columnspan=3,sticky="ew",pady=3)

        lf=ttk.LabelFrame(left,text="PUNTOS DISPONIBLES",style="Card.TLabelframe",padding=6); lf.pack(fill="both",pady=7)
        self.list=tk.Listbox(lf,height=8,exportselection=False); self.list.pack(fill="both",expand=True)
        self.list.bind("<<ListboxSelect>>",self.select_list)

        pf=ttk.LabelFrame(left,text="2. APLICAR PROCESO",style="Card.TLabelframe",padding=8); pf.pack(fill="x")
        ttk.Combobox(pf,textvariable=self.process,values=PROCESSES,state="readonly",width=37).grid(row=0,column=0,columnspan=2,sticky="ew",pady=3)
        ttk.Label(pf,text="Desde").grid(row=1,column=0,sticky="w"); self.cbfrom=ttk.Combobox(pf,textvariable=self.pfrom,state="readonly",width=19); self.cbfrom.grid(row=1,column=1)
        ttk.Label(pf,text="Hasta").grid(row=2,column=0,sticky="w"); self.cbto=ttk.Combobox(pf,textvariable=self.pto,state="readonly",width=19); self.cbto.grid(row=2,column=1)
        ttk.Button(pf,text="APLICAR PROCESO",style="Blue.TButton",command=self.apply_process).grid(row=3,column=0,columnspan=2,sticky="ew",pady=8)
        ttk.Button(pf,text="Borrar procesos",command=self.clear_processes).grid(row=4,column=0,columnspan=2,sticky="ew")

        af=ttk.LabelFrame(left,text="3. ZONA → ADP → BYPASS",style="Card.TLabelframe",padding=8); af.pack(fill="x",pady=7)
        ttk.Label(af,text="Punto de zona R").grid(row=0,column=0,sticky="w")
        self.cbzone=ttk.Combobox(af,textvariable=self.zone_point,state="readonly",width=18); self.cbzone.grid(row=0,column=1,sticky="ew")
        ttk.Label(af,text="Carga sensible").grid(row=1,column=0,sticky="w")
        ttk.Entry(af,textvariable=self.qs,width=14).grid(row=1,column=1,sticky="ew"); ttk.Label(af,text="BTU/h").grid(row=1,column=2)
        ttk.Label(af,text="Carga latente").grid(row=2,column=0,sticky="w")
        ttk.Entry(af,textvariable=self.ql,width=14).grid(row=2,column=1,sticky="ew"); ttk.Label(af,text="BTU/h").grid(row=2,column=2)
        ttk.Label(af,text="Entrada serpentín M/OA").grid(row=3,column=0,sticky="w")
        self.cbin=ttk.Combobox(af,textvariable=self.coil_in,state="readonly",width=18); self.cbin.grid(row=3,column=1,sticky="ew")
        ttk.Label(af,text="Salida serpentín S").grid(row=4,column=0,sticky="w")
        self.cbout=ttk.Combobox(af,textvariable=self.coil_out,state="readonly",width=18); self.cbout.grid(row=4,column=1,sticky="ew")
        ttk.Button(af,text="CALCULAR ADP + BYPASS",style="Blue.TButton",command=self.calculate_adp_bypass).grid(row=5,column=0,columnspan=3,sticky="ew",pady=(8,3))
        ttk.Button(af,text="Limpiar ADP / BF",command=self.clear_adp).grid(row=6,column=0,columnspan=3,sticky="ew")

        hint=ttk.LabelFrame(left,text="MODO INTERACTIVO",style="Card.TLabelframe",padding=8); hint.pack(fill="x",pady=7)
        ttk.Label(hint,text="• Doble clic en la carta: crea un punto.\n• Arrastre un punto: cambia T y W.\n• Clic en un punto: lo selecciona.\n• Edite T/HR en el panel y actualice.\n• Puede encadenar varios procesos.",justify="left").pack(anchor="w")

        self.canvas=tk.Canvas(right,bg="white",highlightthickness=1,highlightbackground="#91bce5")
        self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<Configure>",lambda e:self.draw())
        self.canvas.bind("<Double-Button-1>",self.chart_double)
        self.canvas.bind("<Button-1>",self.chart_down)
        self.canvas.bind("<B1-Motion>",self.chart_drag)
        self.canvas.bind("<ButtonRelease-1>",lambda e:setattr(self,"drag",None))

        bot=ttk.Frame(right); bot.pack(fill="x",pady=(5,0))
        self.props=ttk.Treeview(bot,columns=("value","unit"),show="tree headings",height=7)
        self.props.heading("#0",text="Propiedad"); self.props.heading("value",text="Valor"); self.props.heading("unit",text="Unidad")
        self.props.column("#0",width=170); self.props.column("value",width=100); self.props.column("unit",width=100)
        self.props.pack(side="left",fill="x",expand=True)
        self.procinfo=tk.Text(bot,width=48,height=8); self.procinfo.pack(side="left",padx=(5,0))

    def altv(self): return float(self.alt.get())
    def add_point(self,name,T,RH):
        base=name; i=2
        while name in self.points: name=f"{base}{i}"; i+=1
        self.points[name]=state_trh(T,RH,self.altv()); self.refresh(); self.draw()

    def add_from_form(self):
        try:self.add_point(self.name.get().strip() or f"P{len(self.points)+1}",float(self.t.get()),float(self.rh.get()))
        except Exception as e:messagebox.showerror("Punto",str(e))

    def refresh(self):
        cur=self.selected
        self.list.delete(0,"end")
        names=list(self.points)
        for n in names:self.list.insert("end",n)
        self.cbfrom["values"]=names; self.cbto["values"]=names
        self.cbzone["values"]=names; self.cbin["values"]=names; self.cbout["values"]=names
        if names:
            if self.pfrom.get() not in names:self.pfrom.set(names[0])
            if self.pto.get() not in names:self.pto.set(names[min(1,len(names)-1)])
            if self.zone_point.get() not in names:self.zone_point.set("R" if "R" in names else names[0])
            if self.coil_in.get() not in names:self.coil_in.set("OA" if "OA" in names else names[0])
            if self.coil_out.get() not in names:self.coil_out.set("S" if "S" in names else names[-1])
        self.press.config(text=f"Presión: {p_atm_pa(self.altv())/1000:.2f} kPa  |  {p_atm_pa(self.altv())/3386.389:.2f} inHg")

    def select_list(self,e=None):
        s=self.list.curselection()
        if not s:return
        self.select_name(self.list.get(s[0]))

    def select_name(self,n):
        self.selected=n; q=self.points[n]
        self.name.set(n); self.t.set(f"{q['T']:.2f}"); self.rh.set(f"{q['RH']:.2f}")
        self.show_props(n); self.draw()

    def show_props(self,n):
        for i in self.props.get_children():self.props.delete(i)
        q=self.points[n]
        vals=[("T bulbo seco",q["T"],"°F"),("HR",q["RH"],"%"),("W",q["W"],"lbw/lbda"),("W",q["Wgr"],"grains/lbda"),("Entalpía",q["h"],"Btu/lbda"),("Volumen específico",q["v"],"ft³/lbda"),("Punto de rocío",q["Tdp"],"°F")]
        for a,b,u in vals:self.props.insert("", "end",text=a,values=(f"{b:.4f}",u))

    def update_selected(self):
        if not self.selected:return
        try:
            old=self.selected; new=self.name.get().strip() or old
            q=state_trh(float(self.t.get()),float(self.rh.get()),self.altv())
            if new!=old:
                if new in self.points: raise ValueError("Ya existe un punto con ese nombre.")
                self.points.pop(old); self.points[new]=q
                for p in self.processes:
                    if p["a"]==old:p["a"]=new
                    if p["b"]==old:p["b"]=new
                self.selected=new
            else:self.points[old]=q
            self.refresh(); self.show_props(self.selected); self.draw()
        except Exception as e:messagebox.showerror("Actualizar",str(e))

    def delete_selected(self):
        if not self.selected:return
        n=self.selected; self.points.pop(n,None)
        self.processes=[p for p in self.processes if p["a"]!=n and p["b"]!=n]
        self.selected=None; self.refresh(); self.draw()

    def recalc_all(self):
        try:
            alt=self.altv()
            for n,q in list(self.points.items()):self.points[n]=state_trh(q["T"],q["RH"],alt)
            self.refresh()
            if self.selected:self.show_props(self.selected)
            self.draw()
        except Exception as e:messagebox.showerror("Altitud",str(e))

    def apply_process(self):
        a,b=self.pfrom.get(),self.pto.get()
        if not a or not b or a==b:return messagebox.showwarning("Proceso","Seleccione dos puntos diferentes.")
        self.processes.append({"type":self.process.get(),"a":a,"b":b})
        self.procinfo.delete("1.0","end")
        self.procinfo.insert("end",f"PROCESO APLICADO\n{self.process.get()}\n{a} → {b}\n\nPuede seleccionar otros puntos y agregar otro proceso.")
        self.draw()

    def clear_processes(self): self.processes=[]; self.procinfo.delete("1.0","end"); self.draw()

    def clear_adp(self):
        self.adp_result=None
        self.draw()

    def calculate_adp_bypass(self):
        try:
            zn=self.zone_point.get(); inn=self.coil_in.get(); outn=self.coil_out.get()
            if not zn or not inn or not outn:
                raise ValueError("Seleccione zona, entrada y salida del serpentín.")
            R=self.points[zn]; E=self.points[inn]; S=self.points[outn]
            qs=float(self.qs.get()); ql=float(self.ql.get())
            if qs<=0 or ql<0: raise ValueError("Las cargas deben ser válidas.")
            rshf=qs/(qs+ql)

            # Pendiente de la zona derivada del balance sensible/latente:
            # Qs=1.08*CFM*dT ; Ql=0.68*CFM*dW(gr/lb)
            # dW/dT=(Ql/Qs)*(1.08/0.68), en grains/lb por °F.
            slope=(ql/qs)*(1.08/0.68)

            # Intersección de la línea de pendiente de zona, prolongada desde R,
            # con la curva de saturación. Se busca T_ADP < T_R.
            def f(T):
                wline_gr=R["Wgr"] + slope*(T-R["T"])
                ws_gr=w_from_t_rh(T,100.0,self.altv())*GRAINS
                return wline_gr-ws_gr

            hi=R["T"]-0.01; lo=-20.0
            # localizar cambio de signo robustamente
            prevT=hi; prev=f(prevT); bracket=None
            T=hi-0.25
            while T>=lo:
                cur=f(T)
                if cur==0 or cur*prev<0:
                    bracket=(T,prevT); break
                prevT,prev=T,cur; T-=0.25
            if bracket is None:
                raise ValueError("No se encontró intersección ADP con saturación. Revise cargas y condición de zona.")
            a,b=bracket
            for _ in range(70):
                m=(a+b)/2
                if f(a)*f(m)<=0:b=m
                else:a=m
            tadp=(a+b)/2
            wadp=w_from_t_rh(tadp,100,self.altv())
            adp=state_trh(tadp,100,self.altv())

            # BF real del serpentín usando entrada seleccionada y salida seleccionada.
            denT=E["T"]-tadp
            if abs(denT)<1e-9: raise ValueError("La entrada del serpentín coincide con el ADP.")
            bfT=(S["T"]-tadp)/denT
            denW=E["W"]-wadp
            bfW=None if abs(denW)<1e-12 else (S["W"]-wadp)/denW
            cf=1-bfT
            self.adp_result={"zone":zn,"in":inn,"out":outn,"RSHF":rshf,"slope":slope,
                             "ADP":adp,"BF_T":bfT,"BF_W":bfW,"CF":cf}
            self.procinfo.delete("1.0","end")
            txt=(f"ZONA / ADP / BYPASS\nRSHF = {rshf:.4f}\n"
                 f"Pendiente zona = {slope:.4f} grains/lb·°F\n"
                 f"ADP = {tadp:.2f} °F / 100% HR\n"
                 f"BF temperatura = {bfT:.4f} ({bfT*100:.2f}%)\n"
                 f"CF = {cf:.4f} ({cf*100:.2f}%)\n")
            if bfW is not None:
                txt+=f"BF humedad = {bfW:.4f} ({bfW*100:.2f}%)\nΔBF = {abs(bfT-bfW):.4f}\n"
            if not (0<=bfT<=1):
                txt+="AVISO: BF_T fuera de 0–1. Revise los puntos M/OA, S y la pendiente de zona.\n"
            self.procinfo.insert("end",txt)
            self.draw()
        except Exception as e:
            messagebox.showerror("ADP / Bypass",str(e))

    def bounds(self):return 20,125,0,210
    def xy(self,T,W):
        t0,t1,w0,w1=self.bounds(); cw=max(self.canvas.winfo_width(),700); ch=max(self.canvas.winfo_height(),500)
        ml,mr,mt,mb=58,42,48,52
        return ml+(T-t0)/(t1-t0)*(cw-ml-mr), mt+(w1-W)/(w1-w0)*(ch-mt-mb)
    def invxy(self,x,y):
        t0,t1,w0,w1=self.bounds(); cw=max(self.canvas.winfo_width(),700); ch=max(self.canvas.winfo_height(),500)
        ml,mr,mt,mb=58,42,48,52
        T=t0+(x-ml)/(cw-ml-mr)*(t1-t0); W=w1-(y-mt)/(ch-mt-mb)*(w1-w0)
        return T,W

    def nearest(self,x,y,rad=14):
        best=None; bd=rad
        for n,q in self.points.items():
            px,py=self.xy(q["T"],q["Wgr"]); d=((px-x)**2+(py-y)**2)**.5
            if d<bd:best=n;bd=d
        return best

    def chart_down(self,e):
        n=self.nearest(e.x,e.y)
        if n:self.drag=n; self.select_name(n)

    def chart_drag(self,e):
        if not self.drag:return
        T,Wgr=self.invxy(e.x,e.y); T=max(30,min(125,T)); W=max(0,Wgr/GRAINS)
        ws=w_from_t_rh(T,100,self.altv())
        W=min(W,ws*.999)
        RH=max(.1,min(99.9,rh_from_t_w(T,W,self.altv())))
        self.points[self.drag]=state_trh(T,RH,self.altv())
        self.t.set(f"{T:.2f}"); self.rh.set(f"{RH:.2f}"); self.show_props(self.drag); self.draw()

    def chart_double(self,e):
        T,Wgr=self.invxy(e.x,e.y)
        if not(30<=T<=125 and 0<=Wgr<=210):return
        W=Wgr/GRAINS; ws=w_from_t_rh(T,100,self.altv())
        if W>ws:return
        RH=max(.1,min(99.9,rh_from_t_w(T,W,self.altv())))
        self.add_point(f"P{len(self.points)+1}",T,RH)

    def draw(self):
        c=self.canvas; c.delete("all"); alt=self.altv()
        cw=max(c.winfo_width(),700); ch=max(c.winfo_height(),500)
        c.create_text(68,18,text="CARTA PSICROMÉTRICA PROFESIONAL",anchor="w",
                      fill="#17365d",font=("Segoe UI",15,"bold"))
        c.create_text(68,38,text=f"Altitud {alt:,.0f} m  |  Presión {p_atm_pa(alt)/1000:.2f} kPa  |  ASHRAE-style psychrometric relations",
                      anchor="w",fill="#555",font=("Segoe UI",8))

        # Retícula de bulbo seco
        for T in range(20,126,2):
            x0,y0=self.xy(T,0); x1,y1=self.xy(T,210)
            c.create_line(x0,y0,x1,y1,fill="#ececec",width=1)
            if T%5==0:
                c.create_text(x0,ch-26,text=str(T),anchor="n",fill="#8b1a1a",font=("Segoe UI",7))

        # Retícula W horizontal
        for W in range(0,211,5):
            x0,y0=self.xy(20,W); x1,y1=self.xy(125,W)
            c.create_line(x0,y0,x1,y1,fill="#efefef")
            if W%10==0:
                c.create_text(cw-36,y0,text=str(W),anchor="w",fill="#8b1a1a",font=("Segoe UI",6))

        # HR 10-100 %
        for rh in range(10,101,10):
            pts=[]; lab=None
            for i in range(211):
                T=20+i*.5; W=w_from_t_rh(T,rh,alt)*GRAINS
                if 0<=W<=210:
                    pts+=self.xy(T,W)
                    if 95<T<96: lab=(T,W)
            if len(pts)>3:
                c.create_line(*pts,fill="#a52323",width=2 if rh==100 else 1)
                if lab:
                    x,y=self.xy(*lab); c.create_text(x+3,y-2,text=f"{rh}%",anchor="sw",
                                                     fill="#a52323",font=("Segoe UI",6))

        # Entalpía - diagonales verdes
        for h in range(5,66,2):
            pts=[]
            for i in range(211):
                T=20+i*.5
                w=(h-.240*T)/(1061+.444*T); W=w*GRAINS
                if w>=0 and W<=210 and W<=w_from_t_rh(T,100,alt)*GRAINS:
                    pts+=self.xy(T,W)
            if len(pts)>3:
                c.create_line(*pts,fill="#398b3b",width=1)
                if h%5==0:
                    c.create_text(pts[0]+2,pts[1]-2,text=f"h {h}",anchor="sw",
                                  fill="#26752b",font=("Segoe UI",5))

        # Bulbo húmedo: aproximado mediante línea de entalpía de aire saturado a Twb
        for twb in range(30,86,5):
            ws=w_from_t_rh(twb,100,alt); hs=h_ip(twb,ws); pts=[]
            for i in range(191):
                T=max(20,twb)+i*.5
                if T>125: break
                w=(hs-.240*T)/(1061+.444*T); W=w*GRAINS
                if w>=0 and W<=210 and W<=w_from_t_rh(T,100,alt)*GRAINS:
                    pts+=self.xy(T,W)
            if len(pts)>3:
                c.create_line(*pts,fill="#cc7a00",dash=(2,2),width=1)

        # Volumen específico
        ppsia=p_atm_pa(alt)/6894.757293
        for vt in [12,12.5,13,13.5,14,14.5,15,15.5,16]:
            pts=[]
            for i in range(211):
                T=20+i*.5
                w=((vt*ppsia)/(.370486*(T+459.67))-1)/1.607858
                W=w*GRAINS
                if w>=0 and W<=210 and W<=w_from_t_rh(T,100,alt)*GRAINS:
                    pts+=self.xy(T,W)
            if len(pts)>3:
                c.create_line(*pts,fill="#777",dash=(5,3),width=1)
                c.create_text(pts[-2],pts[-1],text=f"v {vt:g}",anchor="se",
                              fill="#555",font=("Segoe UI",5))

        # Curva de saturación reforzada
        sat=[]
        for i in range(211):
            T=20+i*.5; W=w_from_t_rh(T,100,alt)*GRAINS
            if W<=210:sat+=self.xy(T,W)
        if len(sat)>3:c.create_line(*sat,fill="#8b0000",width=2)

        # Procesos definidos por el usuario
        for p in self.processes:
            if p["a"] not in self.points or p["b"] not in self.points: continue
            a,b=self.points[p["a"]],self.points[p["b"]]
            x1,y1=self.xy(a["T"],a["Wgr"]); x2,y2=self.xy(b["T"],b["Wgr"])
            c.create_line(x1,y1,x2,y2,fill="#006e9e",width=4,arrow="last",arrowshape=(12,14,5))
            c.create_text((x1+x2)/2,(y1+y2)/2-7,text=p["type"],fill="#005271",
                          font=("Segoe UI",7,"bold"))

        # ADP interactivo derivado de la pendiente de zona
        if self.adp_result:
            z=self.points[self.adp_result["zone"]]
            e=self.points[self.adp_result["in"]]
            s=self.points[self.adp_result["out"]]
            a=self.adp_result["ADP"]
            xz,yz=self.xy(z["T"],z["Wgr"]); xa,ya=self.xy(a["T"],a["Wgr"])
            xe,ye=self.xy(e["T"],e["Wgr"]); xs,ys=self.xy(s["T"],s["Wgr"])
            # pendiente de zona R -> ADP
            c.create_line(xz,yz,xa,ya,fill="#7b2cbf",width=3,dash=(8,4))
            c.create_text((xz+xa)/2,(yz+ya)/2-10,text=f"RSHF {self.adp_result['RSHF']:.3f}",
                          fill="#6a1b9a",font=("Segoe UI",8,"bold"))
            # línea ideal de serpentín entrada -> ADP y proceso real entrada -> salida
            c.create_line(xe,ye,xa,ya,fill="#555",width=2,dash=(4,3))
            c.create_line(xe,ye,xs,ys,fill="#0077b6",width=4,arrow="last",arrowshape=(12,14,5))
            c.create_oval(xa-7,ya-7,xa+7,ya+7,fill="#d00000",outline="white",width=2)
            c.create_text(xa+9,ya-8,text=f"ADP {a['T']:.1f}°F",anchor="sw",
                          fill="#a00000",font=("Segoe UI",9,"bold"))
            c.create_text((xe+xs)/2,(ye+ys)/2+12,text=f"BF={self.adp_result['BF_T']:.3f}",
                          fill="#005f8f",font=("Segoe UI",8,"bold"))

        # Puntos interactivos
        for n,q in self.points.items():
            x,y=self.xy(q["T"],q["Wgr"]); sel=n==self.selected; r=7 if sel else 5
            c.create_oval(x-r,y-r,x+r,y+r,fill="#ff9d00" if sel else "#083f9e",
                          outline="white",width=2)
            c.create_text(x+7,y-6,text=n,anchor="sw",fill="#111",font=("Segoe UI",9,"bold"))
            c.create_text(x+7,y+6,text=f"{q['T']:.1f}°F  {q['RH']:.0f}%HR",
                          anchor="nw",fill="#333",font=("Segoe UI",6))

        c.create_text(cw/2,ch-7,text="DRY BULB TEMPERATURE / TEMPERATURA DE BULBO SECO [°F]",
                      fill="#8b1a1a",font=("Segoe UI",8,"bold"))
        c.create_text(cw-10,ch/2,text="HUMIDITY RATIO / RAZÓN DE HUMEDAD [grains/lbda]",
                      angle=90,fill="#8b1a1a",font=("Segoe UI",7,"bold"))

if __name__=="__main__":
    App().mainloop()
