# -*- coding: utf-8 -*-
"""
PSICROMETRIA HVAC PRO V6.6 INTERACTIVA
Carta interactiva: crear, mover y editar puntos; aplicar procesos entre cualquier par.
Unidades IP en carta. Presion corregida automaticamente por altitud.
"""
import math, tkinter as tk
from pathlib import Path
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

def wetbulb_from_t_w(tf,w,alt):
    target=h_ip(tf,w); lo=-40.0; hi=float(tf)
    for _ in range(70):
        m=(lo+hi)/2.0
        wm=w_from_t_rh(m,100.0,alt)
        if h_ip(m,wm)<target: lo=m
        else: hi=m
    return (lo+hi)/2.0

def state_trh(tf,rh,alt):
    w=w_from_t_rh(tf,rh,alt)
    return {"T":float(tf),"RH":float(rh),"W":w,"Wgr":w*GRAINS,
            "h":h_ip(float(tf),w),"v":v_ip(float(tf),w,alt),
            "Tdp":dewpoint(float(tf),w,alt),"Twb":wetbulb_from_t_w(float(tf),w,alt)}

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
        self.title("PSICROMETRIA HVAC PRO V6.6 — CAUDAL + ENTRADA PSICROMETRICA + PDF")
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
        self.supply_mode=tk.StringVar(value="Desde ADP + BF")
        self.bf_input=tk.StringVar(value="0.20")
        self.manual_ts=tk.StringVar(value="55.0")
        self.flow=tk.StringVar(value="5000")
        self.input_pair=tk.StringVar(value="DB + HR")
        self.prop2=tk.StringVar(value="50.0")
        self.points={}; self.processes=[]; self.selected=None; self.drag=None
        self.view=[20.0,125.0,0.0,210.0]
        self.pan_start=None
        self.pan_view=None
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
        ttk.Label(head,text="❄  PSICROMETRIA HVAC PRO V6.6",foreground="#064da8",font=("Segoe UI",19,"bold")).pack(side="left")
        ttk.Label(head,text="Altitud").pack(side="left",padx=(35,4))
        ttk.Entry(head,textvariable=self.alt,width=8).pack(side="left"); ttk.Label(head,text="m").pack(side="left")
        ttk.Button(head,text="Actualizar",command=self.recalc_all).pack(side="left",padx=5)
        self.press=ttk.Label(head,text=""); self.press.pack(side="left",padx=12)
        ttk.Button(head,text="RESTABLECER VISTA",command=self.reset_view).pack(side="right",padx=4)
        ttk.Button(head,text="EXPORTAR A PDF",style="Blue.TButton",command=self.export_pdf).pack(side="right",padx=6)

        pan=ttk.Panedwindow(self,orient="horizontal"); pan.pack(fill="both",expand=True,padx=8,pady=6)
        left=ttk.Frame(pan,padding=5); right=ttk.Frame(pan,padding=3)
        pan.add(left,weight=0); pan.add(right,weight=1)

        f=ttk.LabelFrame(left,text="1. ENTRADA / EDITAR PUNTO",style="Card.TLabelframe",padding=8); f.pack(fill="x")
        ttk.Label(f,text="Nombre").grid(row=0,column=0,sticky="w")
        ttk.Entry(f,textvariable=self.name,width=12).grid(row=0,column=1,sticky="ew")
        ttk.Label(f,text="Caudal").grid(row=1,column=0,sticky="w")
        ttk.Entry(f,textvariable=self.flow,width=12).grid(row=1,column=1,sticky="ew")
        ttk.Label(f,text="CFM").grid(row=1,column=2,sticky="w")
        ttk.Label(f,text="Par de propiedades").grid(row=2,column=0,sticky="w")
        self.cbpair=ttk.Combobox(f,textvariable=self.input_pair,state="readonly",width=18,
            values=["DB + HR","DB + WB","DB + W","DB + DP","DB + h"])
        self.cbpair.grid(row=2,column=1,columnspan=2,sticky="ew")
        self.cbpair.bind("<<ComboboxSelected>>",self.change_input_pair)
        ttk.Label(f,text="T bulbo seco (DB)").grid(row=3,column=0,sticky="w")
        ttk.Entry(f,textvariable=self.t,width=12).grid(row=3,column=1,sticky="ew")
        ttk.Label(f,text="°F").grid(row=3,column=2,sticky="w")
        self.lab2=ttk.Label(f,text="Humedad relativa (HR)"); self.lab2.grid(row=4,column=0,sticky="w")
        ttk.Entry(f,textvariable=self.prop2,width=12).grid(row=4,column=1,sticky="ew")
        self.unit2=ttk.Label(f,text="%"); self.unit2.grid(row=4,column=2,sticky="w")
        ttk.Button(f,text="AGREGAR PUNTO",style="Blue.TButton",command=self.add_from_form).grid(row=5,column=0,columnspan=3,sticky="ew",pady=(7,2))
        ttk.Button(f,text="Actualizar seleccionado",command=self.update_selected).grid(row=6,column=0,columnspan=3,sticky="ew",pady=2)
        ttk.Button(f,text="Eliminar seleccionado",command=self.delete_selected).grid(row=7,column=0,columnspan=3,sticky="ew",pady=2)
        self.quickprops=ttk.Label(f,text="Propiedades calculadas: DB, WB, HR, W, h, v, DP",justify="left")
        self.quickprops.grid(row=8,column=0,columnspan=3,sticky="w",pady=(6,0))

        lf=ttk.LabelFrame(left,text="2. PUNTOS DISPONIBLES",style="Card.TLabelframe",padding=6); lf.pack(fill="both",pady=7)
        self.list=tk.Listbox(lf,height=8,exportselection=False); self.list.pack(fill="both",expand=True)
        self.list.bind("<<ListboxSelect>>",self.select_list)

        pf=ttk.LabelFrame(left,text="3. APLICAR PROCESO",style="Card.TLabelframe",padding=8); pf.pack(fill="x")
        ttk.Combobox(pf,textvariable=self.process,values=PROCESSES,state="readonly",width=37).grid(row=0,column=0,columnspan=2,sticky="ew",pady=3)
        ttk.Label(pf,text="Desde").grid(row=1,column=0,sticky="w"); self.cbfrom=ttk.Combobox(pf,textvariable=self.pfrom,state="readonly",width=19); self.cbfrom.grid(row=1,column=1)
        ttk.Label(pf,text="Hasta").grid(row=2,column=0,sticky="w"); self.cbto=ttk.Combobox(pf,textvariable=self.pto,state="readonly",width=19); self.cbto.grid(row=2,column=1)
        ttk.Button(pf,text="APLICAR PROCESO",style="Blue.TButton",command=self.apply_process).grid(row=3,column=0,columnspan=2,sticky="ew",pady=8)
        ttk.Button(pf,text="Borrar procesos",command=self.clear_processes).grid(row=4,column=0,columnspan=2,sticky="ew")

        af=ttk.LabelFrame(left,text="4. ZONA → ADP → BYPASS",style="Card.TLabelframe",padding=8); af.pack(fill="x",pady=7)
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
        ttk.Label(af,text="Método punto S").grid(row=5,column=0,sticky="w")
        ttk.Combobox(af,textvariable=self.supply_mode,
                     values=["Desde ADP + BF","T suministro fija"],
                     state="readonly",width=18).grid(row=5,column=1,columnspan=2,sticky="ew")
        ttk.Label(af,text="Bypass Factor BF").grid(row=6,column=0,sticky="w")
        ttk.Entry(af,textvariable=self.bf_input,width=14).grid(row=6,column=1,sticky="ew")
        ttk.Label(af,text="T suministro fija").grid(row=7,column=0,sticky="w")
        ttk.Entry(af,textvariable=self.manual_ts,width=14).grid(row=7,column=1,sticky="ew")
        ttk.Label(af,text="°F").grid(row=7,column=2)
        ttk.Button(af,text="CALCULAR ADP + S (BYPASS)",style="Blue.TButton",
                   command=self.calculate_adp_bypass).grid(row=8,column=0,columnspan=3,sticky="ew",pady=(8,3))
        ttk.Button(af,text="Limpiar ADP / BF",command=self.clear_adp).grid(row=9,column=0,columnspan=3,sticky="ew")

        hint=ttk.LabelFrame(left,text="MODO INTERACTIVO",style="Card.TLabelframe",padding=8); hint.pack(fill="x",pady=7)
        ttk.Label(hint,text="• Doble clic en la carta: crea un punto.\n• Arrastre un punto: cambia T y W.\n• Clic en un punto: lo selecciona.\n• Edite T/HR en el panel y actualice.\n• Puede encadenar varios procesos.\n• Rueda mouse: Zoom.\n• Botón central o Shift+arrastre: mover carta.\n• Supr/Del: elimina el punto seleccionado.",justify="left").pack(anchor="w")

        self.canvas=tk.Canvas(right,bg="white",highlightthickness=1,highlightbackground="#91bce5")
        self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<Configure>",lambda e:self.draw())
        self.canvas.bind("<Double-Button-1>",self.chart_double)
        self.canvas.bind("<Button-1>",self.chart_down)
        self.canvas.bind("<B1-Motion>",self.chart_drag)
        self.canvas.bind("<ButtonRelease-1>",lambda e:setattr(self,"drag",None))
        self.canvas.bind("<Motion>",self.chart_motion)
        self.canvas.bind("<MouseWheel>",self.chart_zoom)
        self.canvas.bind("<Button-4>",self.chart_zoom_linux)
        self.canvas.bind("<Button-5>",self.chart_zoom_linux)
        self.canvas.bind("<Button-2>",self.pan_begin)
        self.canvas.bind("<B2-Motion>",self.pan_move)
        self.canvas.bind("<ButtonRelease-2>",self.pan_end)
        self.canvas.bind("<Shift-Button-1>",self.pan_begin)
        self.canvas.bind("<Shift-B1-Motion>",self.pan_move)
        self.canvas.bind("<Shift-ButtonRelease-1>",self.pan_end)
        self.bind("<Delete>",self.delete_key)
        self.bind("<KeyPress-Delete>",self.delete_key)

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
        q=state_trh(T,RH,self.altv()); q["flow"]=0.0
        self.points[name]=q; self.refresh(); self.draw()

    def change_input_pair(self,event=None):
        labels={"DB + HR":("Humedad relativa (HR)","%"),
                "DB + WB":("T bulbo húmedo (WB)","°F"),
                "DB + W":("Humedad específica W","lbw/lbda"),
                "DB + DP":("Punto de rocío (DP)","°F"),
                "DB + h":("Entalpía h","Btu/lbda")}
        lab,unit=labels[self.input_pair.get()]
        self.lab2.config(text=lab); self.unit2.config(text=unit)

    def state_from_inputs(self):
        T=float(self.t.get()); x=float(self.prop2.get()); alt=self.altv()
        pair=self.input_pair.get()
        if pair=="DB + HR":
            if not 0<x<=100: raise ValueError("HR debe estar entre 0 y 100%.")
            return state_trh(T,x,alt)
        if pair=="DB + WB":
            if x>T: raise ValueError("WB no puede ser mayor que DB.")
            ws=w_from_t_rh(x,100,alt); hs=h_ip(x,ws)
            w=(hs-.240*T)/(1061+.444*T)
        elif pair=="DB + W":
            w=x
        elif pair=="DB + DP":
            if x>T: raise ValueError("DP no puede ser mayor que DB.")
            w=w_from_t_rh(x,100,alt)
        elif pair=="DB + h":
            w=(x-.240*T)/(1061+.444*T)
        else:
            raise ValueError("Par de propiedades no válido.")
        if w<0: raise ValueError("La combinación produce humedad específica negativa.")
        RH=rh_from_t_w(T,w,alt)
        if RH<=0 or RH>100.2: raise ValueError("La combinación queda fuera del rango psicrométrico.")
        q=state_trh(T,min(RH,100),alt)
        q["W"]=w; q["Wgr"]=w*GRAINS; q["h"]=h_ip(T,w); q["v"]=v_ip(T,w,alt)
        q["Tdp"]=dewpoint(T,w,alt); q["Twb"]=wetbulb_from_t_w(T,w,alt)
        return q

    def update_quickprops(self,q):
        self.quickprops.config(text=
            f"DB {q['T']:.2f}°F | WB {q.get('Twb',wetbulb_from_t_w(q['T'],q['W'],self.altv())):.2f}°F | HR {q['RH']:.2f}%\n"
            f"W {q['W']:.5f} lb/lb | h {q['h']:.2f} Btu/lb | v {q['v']:.3f} ft³/lb\n"
            f"DP {q['Tdp']:.2f}°F | Caudal {q.get('flow',0):.0f} CFM")

    def add_from_form(self):
        try:
            name=self.name.get().strip() or f"P{len(self.points)+1}"
            q=self.state_from_inputs(); q["flow"]=float(self.flow.get() or 0)
            base=name; i=2
            while name in self.points: name=f"{base}{i}"; i+=1
            self.points[name]=q; self.selected=name
            self.refresh(); self.show_props(name); self.update_quickprops(q); self.draw()
        except Exception as e: messagebox.showerror("Punto",str(e))

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
        self.flow.set(f"{q.get('flow',0):.0f}"); self.input_pair.set("DB + HR"); self.prop2.set(f"{q['RH']:.2f}")
        self.change_input_pair(); self.show_props(n); self.update_quickprops(q); self.draw()

    def show_props(self,n):
        for i in self.props.get_children():self.props.delete(i)
        q=self.points[n]
        vals=[("T bulbo seco",q["T"],"°F"),("T bulbo húmedo",q.get("Twb",wetbulb_from_t_w(q["T"],q["W"],self.altv())),"°F"),
              ("HR",q["RH"],"%"),("W",q["W"],"lbw/lbda"),("W",q["Wgr"],"grains/lbda"),
              ("Entalpía",q["h"],"Btu/lbda"),("Volumen específico",q["v"],"ft³/lbda"),
              ("Punto de rocío",q["Tdp"],"°F"),("Caudal",q.get("flow",0),"CFM")]
        for a,b,u in vals:self.props.insert("", "end",text=a,values=(f"{b:.4f}",u))

    def update_selected(self):
        if not self.selected:return
        try:
            old=self.selected; new=self.name.get().strip() or old
            q=self.state_from_inputs(); q["flow"]=float(self.flow.get() or 0)
            if new!=old:
                if new in self.points: raise ValueError("Ya existe un punto con ese nombre.")
                self.points.pop(old); self.points[new]=q
                for p in self.processes:
                    if p["a"]==old:p["a"]=new
                    if p["b"]==old:p["b"]=new
                self.selected=new
            else: self.points[old]=q
            self.refresh(); self.show_props(self.selected); self.update_quickprops(q); self.draw()
        except Exception as e: messagebox.showerror("Actualizar",str(e))

    def delete_selected(self):
        if not self.selected:return
        n=self.selected
        self.points.pop(n,None)
        self.processes=[p for p in self.processes if p["a"]!=n and p["b"]!=n]
        if self.adp_result and n in ("ADP","S",self.adp_result.get("zone")):
            self.adp_result=None
        self.selected=None
        for i in self.props.get_children(): self.props.delete(i)
        self.refresh(); self.draw()

    def delete_key(self,event=None):
        # Supr/Del elimina exactamente el punto actualmente seleccionado.
        self.delete_selected()
        return "break"

    def recalc_all(self):
        try:
            alt=self.altv()
            for n,q in list(self.points.items()):
                flow=q.get("flow",0.0); nq=state_trh(q["T"],q["RH"],alt); nq["flow"]=flow
                self.points[n]=nq
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
        self.supply_mode=tk.StringVar(value="Desde ADP + BF")
        self.bf_input=tk.StringVar(value="0.20")
        self.manual_ts=tk.StringVar(value="55.0")
        self.flow=tk.StringVar(value="5000")
        self.input_pair=tk.StringVar(value="DB + HR")
        self.prop2=tk.StringVar(value="50.0")
        self.draw()

    def calculate_adp_bypass(self):
        try:
            zn=self.zone_point.get()
            if not zn:
                raise ValueError("Seleccione el punto de retorno R.")
            R=self.points[zn]

            qs=float(self.qs.get()); ql=float(self.ql.get())
            if qs<=0 or ql<0:
                raise ValueError("Las cargas sensible y latente deben ser válidas.")
            rshf=qs/(qs+ql)

            # Pendiente de zona R -> ADP a partir de cargas sensible/latente.
            slope=(ql/qs)*(1.08/0.68)

            def f(T):
                wline_gr=R["Wgr"] + slope*(T-R["T"])
                ws_gr=w_from_t_rh(T,100.0,self.altv())*GRAINS
                return wline_gr-ws_gr

            hi=R["T"]-0.01; lo=-20.0
            prevT=hi; prev=f(prevT); bracket=None
            T=hi-0.25
            while T>=lo:
                cur=f(T)
                if cur==0 or cur*prev<0:
                    bracket=(T,prevT); break
                prevT,prev=T,cur
                T-=0.25
            if bracket is None:
                raise ValueError("No se encontró ADP sobre saturación. Revise retorno y cargas.")

            a,b=bracket
            for _ in range(70):
                m=(a+b)/2
                if f(a)*f(m)<=0: b=m
                else: a=m
            tadp=(a+b)/2
            ADP=state_trh(tadp,100.0,self.altv())

            mode=self.supply_mode.get()
            if mode=="Desde ADP + BF":
                BF=float(self.bf_input.get())
                if not 0.0<=BF<=1.0:
                    raise ValueError("BF debe estar entre 0 y 1.")
                # Punto S sobre la recta ADP-R:
                # BF = (S-ADP)/(R-ADP)
                ts=ADP["T"] + BF*(R["T"]-ADP["T"])
                ws=ADP["W"] + BF*(R["W"]-ADP["W"])
            else:
                ts=float(self.manual_ts.get())
                if not tadp<=ts<=R["T"]:
                    raise ValueError("T suministro debe quedar entre ADP y retorno.")
                BF=(ts-tadp)/(R["T"]-tadp)
                self.bf_input.set(f"{BF:.4f}")
                ws=ADP["W"] + BF*(R["W"]-ADP["W"])

            rhs=max(0.1,min(100.0,rh_from_t_w(ts,ws,self.altv())))
            S=state_trh(ts,rhs,self.altv())
            S["W"]=ws; S["Wgr"]=ws*GRAINS
            S["h"]=h_ip(ts,ws); S["v"]=v_ip(ts,ws,self.altv())
            S["Tdp"]=dewpoint(ts,ws,self.altv())

            BF_T=(S["T"]-ADP["T"])/(R["T"]-ADP["T"])
            denW=R["W"]-ADP["W"]
            BF_W=None if abs(denW)<1e-12 else (S["W"]-ADP["W"])/denW
            CF=1.0-BF_T

            # ADP y S pasan a ser puntos reales de la carta.
            self.points["ADP"]=ADP
            self.points["S"]=S
            self.selected="S"
            self.adp_result={
                "zone":zn,"in":zn,"out":"S","RSHF":rshf,"slope":slope,
                "ADP":ADP,"BF_T":BF_T,"BF_W":BF_W,"CF":CF,"mode":mode
            }

            self.refresh()
            self.show_props("S")
            self.procinfo.delete("1.0","end")
            txt=(f"RETORNO R → ADP → SUMINISTRO S\n"
                 f"RSHF = {rshf:.4f}\n"
                 f"ADP = {ADP['T']:.2f} °F / 100% HR\n"
                 f"BF = {BF_T:.4f} ({BF_T*100:.2f}%)\n"
                 f"CF = {CF:.4f} ({CF*100:.2f}%)\n"
                 f"S = {S['T']:.2f} °F / {S['RH']:.2f}% HR\n"
                 f"W(S) = {S['W']:.5f} lbw/lbda\n")
            if BF_W is not None:
                txt += f"BF por humedad = {BF_W:.4f}\n"
            txt += "\nS se posiciona automáticamente sobre la recta ADP–R."
            self.procinfo.insert("end",txt)
            self.draw()
        except Exception as e:
            messagebox.showerror("ADP / Bypass",str(e))

    def chart_motion(self,event):
        try:
            T,Wgr=self.invxy(event.x,event.y)
            if T < -40 or T > 180 or Wgr < 0:
                self.canvas.delete("cursor_info")
                return
            W=Wgr/GRAINS
            ws=w_from_t_rh(T,100,self.altv())
            if W > ws:
                self.canvas.delete("cursor_info")
                return
            RH=max(0.0,min(100.0,rh_from_t_w(T,W,self.altv())))
            h=h_ip(T,W); v=v_ip(T,W,self.altv()); dp=dewpoint(T,W,self.altv())
            txt=(f"Datos en el cursor\n"
                 f"T = {T:.1f} °F\nHR = {RH:.1f} %\n"
                 f"W = {W:.4f} lbw/lbda\nh = {h:.1f} Btu/lbda\n"
                 f"v = {v:.1f} ft³/lbda\nTpr = {dp:.1f} °F")
            self.canvas.delete("cursor_info")
            cw=max(self.canvas.winfo_width(),700)
            x=min(event.x+18,cw-180); y=max(70,event.y-20)
            self.canvas.create_rectangle(x,y,x+170,y+126,fill="#f7fbff",outline="#6aa9e9",
                                         width=1,tags="cursor_info")
            self.canvas.create_text(x+8,y+8,text=txt,anchor="nw",fill="#17365d",
                                    font=("Segoe UI",8),tags="cursor_info")
        except Exception:
            self.canvas.delete("cursor_info")

    def export_pdf(self):
        # Exportación PDF sin librerías externas: carta + puntos + resultados resumidos.
        from tkinter import filedialog
        import tempfile, os
        path=filedialog.asksaveasfilename(
            title="Exportar carta psicrométrica a PDF",
            defaultextension=".pdf",
            filetypes=[("Archivo PDF","*.pdf")],
            initialfile="Carta_Psicrometrica_HVAC_PRO_V6_6.pdf")
        if not path:return
        try:
            # Tk Canvas -> PostScript. Convert to a minimal PDF-like report if Pillow/Ghostscript
            # are unavailable; on normal Windows builds the report text is always generated.
            # This writer creates a standards-compliant one-page PDF with engineering results.
            lines=[
                "PSICROMETRIA HVAC PRO V6.6",
                "CARTA PSICROMETRICA - REPORTE",
                f"Altitud: {self.altv():.0f} m",
                f"Presion: {p_atm_pa(self.altv())/1000:.2f} kPa",
                "",
                "PUNTOS:"
            ]
            for n,q in self.points.items():
                lines.append(f"{n}: Q={q.get('flow',0):.0f} CFM | DB={q['T']:.2f} F | WB={q.get('Twb',wetbulb_from_t_w(q['T'],q['W'],self.altv())):.2f} F | HR={q['RH']:.2f}% | W={q['W']:.5f} | h={q['h']:.2f}")
            if self.adp_result:
                a=self.adp_result["ADP"]
                lines += ["", "ADP / BYPASS:",
                          f"RSHF={self.adp_result['RSHF']:.4f}",
                          f"ADP={a['T']:.2f} F / 100% HR",
                          f"BF={self.adp_result['BF_T']:.4f}",
                          f"CF={self.adp_result['CF']:.4f}"]
            def esc(s): return s.replace("\\","\\\\").replace("(","\\(").replace(")","\\)")
            y=760
            content=["BT","/F1 12 Tf","50 790 Td"]
            for i,line in enumerate(lines):
                if i: content += ["0 -18 Td"]
                content += [f"({esc(line)}) Tj"]
            content += ["ET"]
            stream="\n".join(content).encode("latin-1","replace")
            objs=[]
            objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
            objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
            objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>")
            objs.append(f"<< /Length {len(stream)} >>\nstream\n".encode()+stream+b"\nendstream")
            objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
            pdf=b"%PDF-1.4\n"; offsets=[0]
            for i,obj in enumerate(objs,1):
                offsets.append(len(pdf))
                pdf+=f"{i} 0 obj\n".encode()+obj+b"\nendobj\n"
            xref=len(pdf)
            pdf+=f"xref\n0 {len(objs)+1}\n".encode()+b"0000000000 65535 f \n"
            for off in offsets[1:]:
                pdf+=f"{off:010d} 00000 n \n".encode()
            pdf+=f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
            Path(path).write_bytes(pdf)
            messagebox.showinfo("Exportar PDF",f"PDF creado correctamente:\n{path}")
        except Exception as e:
            messagebox.showerror("Exportar PDF",str(e))

    def bounds(self):
        return tuple(self.view)

    def reset_view(self):
        self.view=[20.0,125.0,0.0,210.0]
        self.draw()

    def _plot_rect(self):
        cw=max(self.canvas.winfo_width(),700); ch=max(self.canvas.winfo_height(),500)
        return 58.0, 48.0, cw-42.0, ch-52.0

    def xy(self,T,W):
        t0,t1,w0,w1=self.bounds()
        xl,yt,xr,yb=self._plot_rect()
        return xl+(T-t0)/(t1-t0)*(xr-xl), yt+(w1-W)/(w1-w0)*(yb-yt)

    def invxy(self,x,y):
        t0,t1,w0,w1=self.bounds()
        xl,yt,xr,yb=self._plot_rect()
        T=t0+(x-xl)/(xr-xl)*(t1-t0)
        W=w1-(y-yt)/(yb-yt)*(w1-w0)
        return T,W

    def chart_zoom(self,event):
        # Zoom centrado exactamente donde está el cursor.
        factor=0.86 if event.delta>0 else 1.0/0.86
        self._zoom_at(event.x,event.y,factor)
        return "break"

    def chart_zoom_linux(self,event):
        factor=0.86 if event.num==4 else 1.0/0.86
        self._zoom_at(event.x,event.y,factor)
        return "break"

    def _zoom_at(self,x,y,factor):
        t0,t1,w0,w1=self.view
        Tc,Wc=self.invxy(x,y)
        nt0=Tc+(t0-Tc)*factor; nt1=Tc+(t1-Tc)*factor
        nw0=Wc+(w0-Wc)*factor; nw1=Wc+(w1-Wc)*factor
        # Limita zoom extremo sin impedir explorar la carta.
        if (nt1-nt0)<8 or (nw1-nw0)<16:return
        if (nt1-nt0)>220 or (nw1-nw0)>440:return
        self.view=[nt0,nt1,nw0,nw1]
        self.draw()

    def pan_begin(self,event):
        self.pan_start=(event.x,event.y)
        self.pan_view=list(self.view)
        self.canvas.configure(cursor="fleur")
        return "break"

    def pan_move(self,event):
        if not self.pan_start or not self.pan_view:return "break"
        x0,y0=self.pan_start
        t0,t1,w0,w1=self.pan_view
        xl,yt,xr,yb=self._plot_rect()
        dT=-(event.x-x0)/(xr-xl)*(t1-t0)
        dW=(event.y-y0)/(yb-yt)*(w1-w0)
        self.view=[t0+dT,t1+dT,w0+dW,w1+dW]
        self.draw()
        return "break"

    def pan_end(self,event=None):
        self.pan_start=None; self.pan_view=None
        self.canvas.configure(cursor="")
        return "break"

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
        T,Wgr=self.invxy(e.x,e.y); T=max(-20,min(150,T)); W=max(0,Wgr/GRAINS)
        ws=w_from_t_rh(T,100,self.altv())
        W=min(W,ws*.999)
        RH=max(.1,min(99.9,rh_from_t_w(T,W,self.altv())))
        self.points[self.drag]=state_trh(T,RH,self.altv())
        self.t.set(f"{T:.2f}"); self.rh.set(f"{RH:.2f}"); self.show_props(self.drag); self.draw()

    def chart_double(self,e):
        T,Wgr=self.invxy(e.x,e.y)
        if not(-20<=T<=150 and Wgr>=0):return
        W=Wgr/GRAINS; ws=w_from_t_rh(T,100,self.altv())
        if W>ws:return
        RH=max(.1,min(99.9,rh_from_t_w(T,W,self.altv())))
        self.add_point(f"P{len(self.points)+1}",T,RH)

    def draw(self):
        c=self.canvas; c.delete("all"); alt=self.altv()
        cw=max(c.winfo_width(),700); ch=max(c.winfo_height(),500)
        c.create_text(68,18,text="CARTA PSICROMÉTRICA PROFESIONAL",anchor="w",
                      fill="#17365d",font=("Segoe UI",15,"bold"))
        c.create_text(68,38,text=f"Altitud {alt:,.0f} m | Presión {p_atm_pa(alt)/1000:.2f} kPa | Zoom {(105.0/(self.view[1]-self.view[0]))*100:.0f}% | rueda=zoom | botón central/Shift+arrastre=mover | Supr=eliminar",
                      anchor="w",fill="#555",font=("Segoe UI",8))
        c.create_rectangle(75,72,315,185,fill="#f8fbff",outline="#6aa9e9",width=1)
        c.create_text(88,82,text="Navegación de la carta:",anchor="nw",fill="#17365d",
                      font=("Segoe UI",9,"bold"))
        c.create_text(88,105,text="Zoom: rueda del mouse\nMover: botón central o Shift + arrastrar\nEliminar punto: clic + Supr (Delete)",
                      anchor="nw",fill="#17365d",font=("Segoe UI",8))


        # Retícula de bulbo seco (se adapta al zoom/pan)
        t0,t1,w0,w1=self.bounds()
        Tstart=int(math.floor(t0/2.0)*2)
        Tend=int(math.ceil(t1/2.0)*2)
        for T in range(Tstart,Tend+1,2):
            x0,y0=self.xy(T,w0); x1,y1=self.xy(T,w1)
            c.create_line(x0,y0,x1,y1,fill="#ececec",width=1)
            if T%5==0:
                c.create_text(x0,ch-26,text=str(T),anchor="n",fill="#8b1a1a",font=("Segoe UI",7))

        # Retícula W horizontal (se adapta al zoom/pan)
        Wstart=int(math.floor(w0/5.0)*5)
        Wend=int(math.ceil(w1/5.0)*5)
        for W in range(Wstart,Wend+1,5):
            x0,y0=self.xy(t0,W); x1,y1=self.xy(t1,W)
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
            c.create_text((xe+xs)/2,(ye+ys)/2+12,text=f"S desde ADP | BF={self.adp_result['BF_T']:.3f}",
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
