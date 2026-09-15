# -*- coding: utf-8 -*-
"""
Psicrometria HVAC PRO V5.2 - FUENTE EDITABLE (REV B - BYPASS FACTOR)
Mejora: cálculo automático de RSHF y ADP a partir de cargas sensible y latente.

NOTA:
El EXE original fue empaquetado con PyInstaller/Python 3.12. El fuente literal no
estaba dentro del ejecutable. Esta versión reconstruye una base editable y conserva
el enfoque de la V5.1: propiedades psicrométricas, carta interactiva y ADP.
"""
import math
import tkinter as tk
from tkinter import ttk, messagebox

GRAINS_PER_LB = 7000.0

def p_atm_pa(alt_ft):
    h = float(alt_ft) * 0.3048
    return 101325.0 * (1.0 - 2.25577e-5 * h) ** 5.2559

def pws_pa_f(t_f):
    # ASHRAE-style saturation pressure correlation (valid for HVAC range)
    t_c = (float(t_f) - 32.0) * 5.0 / 9.0
    T = t_c + 273.15
    if t_c >= 0:
        ln_pws = (-5.8002206e3/T + 1.3914993 - 4.8640239e-2*T
                  + 4.1764768e-5*T*T - 1.4452093e-8*T**3
                  + 6.5459673*math.log(T))
    else:
        ln_pws = (-5.6745359e3/T + 6.3925247 - 9.677843e-3*T
                  + 6.2215701e-7*T*T + 2.0747825e-9*T**3
                  - 9.484024e-13*T**4 + 4.1635019*math.log(T))
    return math.exp(ln_pws)

def w_from_t_rh(t_f, rh_pct, alt_ft=0):
    p = p_atm_pa(alt_ft)
    pw = max(0.0, min(1.0, float(rh_pct)/100.0)) * pws_pa_f(t_f)
    return 0.621945 * pw / max(p - pw, 1.0)

def rh_from_t_w(t_f, w, alt_ft=0):
    p = p_atm_pa(alt_ft)
    pw = p * w / (0.621945 + w)
    return 100.0 * pw / pws_pa_f(t_f)

def enthalpy_btu_lb(t_f, w):
    return 0.240 * t_f + w * (1061.0 + 0.444 * t_f)

def dew_point_f_from_w(w, alt_ft=0):
    p = p_atm_pa(alt_ft)
    pw = p * w / (0.621945 + w)
    lo, hi = -40.0, 140.0
    for _ in range(80):
        mid = (lo + hi)/2
        if pws_pa_f(mid) < pw: lo = mid
        else: hi = mid
    return (lo + hi)/2

def state_from_t_rh(t_f, rh_pct, alt_ft=0):
    w = w_from_t_rh(t_f, rh_pct, alt_ft)
    return {
        "T": float(t_f), "RH": float(rh_pct), "W": w,
        "Wgr": w*GRAINS_PER_LB,
        "h": enthalpy_btu_lb(float(t_f), w),
        "Tdp": dew_point_f_from_w(w, alt_ft)
    }

def adp_from_room_loads(t_room_f, rh_room_pct, q_sensible, q_latent, alt_ft=0):
    """
    Línea RSHF usando:
       Qs = 1.08 * CFM * ΔT
       Ql = 0.68 * CFM * Δgrains
    => Δgrains/ΔT = (Ql/Qs)*(1.08/0.68)
    El ADP es la intersección de esa línea extendida con HR=100%.
    """
    qs = float(q_sensible)
    ql = float(q_latent)
    if qs <= 0 or ql < 0:
        raise ValueError("La carga sensible debe ser > 0 y la latente >= 0.")
    rshf = qs/(qs+ql)
    room = state_from_t_rh(t_room_f, rh_room_pct, alt_ft)
    slope_gr_f = (ql/qs) * (1.08/0.68) if ql > 0 else 0.0

    def f(t):
        wsat_gr = w_from_t_rh(t, 100.0, alt_ft)*GRAINS_PER_LB
        line_gr = room["Wgr"] - slope_gr_f*(room["T"]-t)
        return wsat_gr - line_gr

    # Buscar la raíz por barrido y bisección, desde muy frío hasta el recinto.
    tmin = max(-20.0, room["T"]-100.0)
    xs = [tmin + i*(room["T"]-tmin)/400.0 for i in range(401)]
    root = None
    last_t, last_f = xs[0], f(xs[0])
    for t in xs[1:]:
        ft = f(t)
        if ft == 0 or ft*last_f < 0:
            lo, hi = last_t, t
            for _ in range(70):
                m = (lo+hi)/2
                fm = f(m)
                if f(lo)*fm <= 0: hi = m
                else: lo = m
            root = (lo+hi)/2
        last_t, last_f = t, ft
    if root is None:
        raise ValueError("No se encontró una intersección física con saturación para estas cargas.")
    wadp = w_from_t_rh(root, 100.0, alt_ft)
    return {
        "RSHF": rshf,
        "ADP_F": root,
        "ADP_C": (root-32)*5/9,
        "W_ADP": wadp,
        "W_ADP_gr": wadp*GRAINS_PER_LB,
        "h_ADP": enthalpy_btu_lb(root, wadp),
        "room": room,
        "slope_gr_f": slope_gr_f,
    }


def supply_from_room_loads(t_room_f, rh_room_pct, q_sensible, q_latent,
                           t_supply_f, alt_ft=0):
    """Supply state constrained to the room RSHF line."""
    base = adp_from_room_loads(t_room_f, rh_room_pct, q_sensible, q_latent, alt_ft)
    room = base["room"]
    ts = float(t_supply_f)
    if ts >= room["T"]:
        raise ValueError("La temperatura de suministro debe ser menor que la del recinto.")
    ws_gr = room["Wgr"] - base["slope_gr_f"] * (room["T"] - ts)
    ws = ws_gr / GRAINS_PER_LB
    rhs = rh_from_t_w(ts, ws, alt_ft)
    if ws <= 0 or rhs <= 0 or rhs > 100.0:
        raise ValueError("La temperatura de suministro elegida no produce un estado psicrométrico físico sobre la línea RSHF.")
    cfm = float(q_sensible) / (1.08 * (room["T"] - ts))
    bf = (ts - base["ADP_F"]) / (room["T"] - base["ADP_F"])
    cf = 1.0 - bf
    return {
        **base, "T_supply_F": ts, "W_supply": ws, "W_supply_gr": ws_gr,
        "RH_supply": rhs, "h_supply": enthalpy_btu_lb(ts, ws),
        "CFM": cfm, "BF": bf, "CF": cf
    }

def mixed_air_state(t_oa_f, rh_oa, t_ra_f, rh_ra, oa_fraction, alt_ft=0):
    x = float(oa_fraction)
    if not 0 <= x <= 1:
        raise ValueError("La fracción de aire exterior debe estar entre 0 y 1.")
    oa = state_from_t_rh(t_oa_f, rh_oa, alt_ft)
    ra = state_from_t_rh(t_ra_f, rh_ra, alt_ft)
    w = x*oa["W"] + (1-x)*ra["W"]
    h = x*oa["h"] + (1-x)*ra["h"]
    # Solve dry-bulb from h = 0.24T + W(1061+0.444T)
    t = (h - 1061*w) / (0.240 + 0.444*w)
    return {"T":t, "W":w, "Wgr":w*GRAINS_PER_LB,
            "RH":rh_from_t_w(t,w,alt_ft), "h":h, "OA":oa, "RA":ra}


def coil_bypass_factor(t_enter_f, w_enter, t_leave_f, w_leave, t_adp_f, w_adp):
    """Calcula BF por temperatura, BF por humedad y Contact Factor."""
    dt = float(t_enter_f) - float(t_adp_f)
    dw = float(w_enter) - float(w_adp)
    if abs(dt) < 1e-9:
        raise ValueError("T entrada y T ADP no pueden ser iguales.")
    bf_t = (float(t_leave_f) - float(t_adp_f)) / dt
    bf_w = None if abs(dw) < 1e-12 else (float(w_leave) - float(w_adp)) / dw
    cf = 1.0 - bf_t
    return {
        "BF_T": bf_t, "BF_W": bf_w, "CF": cf,
        "BYPASS_PCT": 100.0*bf_t, "CONTACT_PCT": 100.0*cf,
        "delta_BF": None if bf_w is None else abs(bf_t-bf_w)
    }

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Psicrometría HVAC PRO V5.2 — ADP + Serpentín + Aire de Suministro")
        self.geometry("1280x780")
        self.minsize(1050, 680)
        self._build()

    def _entry(self, parent, row, label, default, unit):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=5)
        v = tk.StringVar(value=str(default))
        ttk.Entry(parent, textvariable=v, width=14).grid(row=row, column=1, padx=6, pady=5)
        ttk.Label(parent, text=unit).grid(row=row, column=2, sticky="w")
        return v

    def _build(self):
        top = ttk.Frame(self, padding=10); top.pack(fill="x")
        ttk.Label(top, text="PSICROMETRÍA HVAC PRO V5.2", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Label(top, text="  |  ADP automático por carga sensible y latente").pack(side="left")

        main = ttk.Panedwindow(self, orient="horizontal"); main.pack(fill="both", expand=True, padx=10, pady=(0,10))
        left = ttk.Frame(main, padding=10); right = ttk.Frame(main, padding=5)
        main.add(left, weight=0); main.add(right, weight=1)

        box = ttk.LabelFrame(left, text="Datos del recinto y cargas", padding=8)
        box.pack(fill="x")
        self.alt = self._entry(box,0,"Altitud",3250,"ft")
        self.tr = self._entry(box,1,"T. recinto",75,"°F")
        self.rh = self._entry(box,2,"HR recinto",50,"%")
        self.qs = self._entry(box,3,"Carga sensible",80000,"BTU/h")
        self.ql = self._entry(box,4,"Carga latente",20000,"BTU/h")
        self.ts = self._entry(box,5,"T. suministro",55,"°F")
        ttk.Button(box,text="CALCULAR RSHF + ADP + SUMINISTRO",command=self.calculate_adp).grid(row=6,column=0,columnspan=3,sticky="ew",pady=10)

        mix = ttk.LabelFrame(left, text="Mezcla de aire OA + RA", padding=8)
        mix.pack(fill="x", pady=(8,0))
        self.toa = self._entry(mix,0,"T. exterior",92,"°F")
        self.rhoa = self._entry(mix,1,"HR exterior",55,"%")
        self.oap = self._entry(mix,2,"Aire exterior",20,"%")
        ttk.Button(mix,text="CALCULAR MEZCLA",command=self.calculate_mix).grid(row=3,column=0,columnspan=3,sticky="ew",pady=8)
        ttk.Button(mix,text="CALCULAR BYPASS SERPENTÍN",command=self.calculate_bypass).grid(row=4,column=0,columnspan=3,sticky="ew",pady=(0,8))

        out = ttk.LabelFrame(left,text="Resultados",padding=8); out.pack(fill="x",pady=10)
        self.result = tk.Text(out,width=38,height=14,font=("Consolas",10))
        self.result.pack(fill="both")

        note = ("Método: RSHF = Qs/(Qs+Ql). La pendiente humedad/temperatura se obtiene "
                "de 1.08·CFM·ΔT y 0.68·CFM·Δgrains. La línea se prolonga desde el recinto "
                "hasta HR=100 %, obteniendo el ADP.")
        ttk.Label(left,text=note,wraplength=330,justify="left").pack(fill="x",pady=4)

        self.canvas = tk.Canvas(right,bg="white",highlightthickness=1,highlightbackground="#999")
        self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<Configure>",lambda e:self.draw_chart())

        self.last = None
        self.mix_state = None
        self.after(100,self.calculate_adp)

    def chart_bounds(self):
        return 30.0, 110.0, 0.0, 180.0

    def xy(self,T,Wgr):
        t0,t1,w0,w1=self.chart_bounds()
        cw=max(self.canvas.winfo_width(),600); ch=max(self.canvas.winfo_height(),500)
        ml,mr,mt,mb=60,25,30,55
        x=ml+(T-t0)/(t1-t0)*(cw-ml-mr)
        y=mt+(w1-Wgr)/(w1-w0)*(ch-mt-mb)
        return x,y

    def draw_chart(self):
        c=self.canvas; c.delete("all")
        t0,t1,w0,w1=self.chart_bounds()
        cw=max(c.winfo_width(),600); ch=max(c.winfo_height(),500)
        # grid
        for T in range(30,111,10):
            x0,y0=self.xy(T,0); x1,y1=self.xy(T,180)
            c.create_line(x0,y0,x1,y1,fill="#e6e6e6")
            c.create_text(x0,ch-28,text=str(T),anchor="n")
        for W in range(0,181,20):
            x0,y0=self.xy(30,W); x1,y1=self.xy(110,W)
            c.create_line(x0,y0,x1,y1,fill="#ededed")
            c.create_text(52,y0,text=str(W),anchor="e")
        c.create_text(cw/2,ch-8,text="Temperatura de bulbo seco [°F]")
        c.create_text(14,ch/2,text="Razón de humedad [grains/lb]",angle=90)

        # RH curves
        alt=float(self.alt.get() or 0)
        for rh in range(10,101,10):
            pts=[]
            for i in range(161):
                T=30+i*0.5
                W=w_from_t_rh(T,rh,alt)*GRAINS_PER_LB
                if 0<=W<=180: pts += self.xy(T,W)
            if len(pts)>=4:
                c.create_line(*pts,fill="#b0b0b0",width=2 if rh==100 else 1)
        c.create_text(*self.xy(57, w_from_t_rh(57,100,alt)*7000),text="100% HR",anchor="sw")

        if self.last:
            d=self.last; r=d["room"]
            # extended RSHF line from ADP through room
            xa,ya=self.xy(d["ADP_F"],d["W_ADP_gr"])
            xr,yr=self.xy(r["T"],r["Wgr"])
            c.create_line(xa,ya,xr,yr,width=3,arrow="last")
            c.create_oval(xa-5,ya-5,xa+5,ya+5,fill="black")
            c.create_text(xa+8,ya-8,text=f"ADP {d['ADP_F']:.1f}°F",anchor="sw",font=("Segoe UI",10,"bold"))
            c.create_oval(xr-5,yr-5,xr+5,yr+5,fill="black")
            c.create_text(xr+8,yr-8,text=f"R {r['T']:.1f}°F / {r['RH']:.0f}% HR",anchor="sw",font=("Segoe UI",10,"bold"))
            if "T_supply_F" in d:
                xs,ys=self.xy(d["T_supply_F"],d["W_supply_gr"])
                c.create_oval(xs-5,ys-5,xs+5,ys+5,fill="black")
                c.create_text(xs+8,ys+8,text=f"S {d['T_supply_F']:.1f}°F",anchor="nw",font=("Segoe UI",10,"bold"))
                c.create_line(xs,ys,xr,yr,width=3)
            if getattr(self, "mix_state", None):
                m=self.mix_state
                xm,ym=self.xy(m["T"],m["Wgr"])
                xo,yo=self.xy(m["OA"]["T"],m["OA"]["Wgr"])
                c.create_line(xo,yo,xr,yr,width=2,dash=(5,3))
                c.create_oval(xm-5,ym-5,xm+5,ym+5,fill="black")
                c.create_text(xm+8,ym-8,text="M",anchor="sw",font=("Segoe UI",10,"bold"))

    def calculate_adp(self):
        try:
            d=supply_from_room_loads(float(self.tr.get()),float(self.rh.get()),
                                     float(self.qs.get()),float(self.ql.get()),
                                     float(self.ts.get()),float(self.alt.get()))
            self.last=d
            self.result.delete("1.0","end")
            self.result.insert("end",
                f"RSHF             = {d['RSHF']:.4f}\n"
                f"ADP              = {d['ADP_F']:.2f} °F / {d['ADP_C']:.2f} °C\n"
                f"W ADP            = {d['W_ADP_gr']:.2f} grains/lb\n"
                f"h ADP            = {d['h_ADP']:.2f} BTU/lb\n"
                f"\nAIRE DE SUMINISTRO\n"
                f"T suministro     = {d['T_supply_F']:.2f} °F\n"
                f"HR suministro    = {d['RH_supply']:.2f} %\n"
                f"W suministro     = {d['W_supply_gr']:.2f} grains/lb\n"
                f"h suministro     = {d['h_supply']:.2f} BTU/lb\n"
                f"Caudal requerido = {d['CFM']:.0f} CFM\n"
                f"BF               = {d['BF']:.4f}\n"
                f"CF               = {d['CF']:.4f}\n"
                f"\nRECINTO\n"
                f"Tdb              = {d['room']['T']:.2f} °F\n"
                f"HR               = {d['room']['RH']:.2f} %\n"
                f"W                 = {d['room']['Wgr']:.2f} grains/lb\n"
                f"h                 = {d['room']['h']:.2f} BTU/lb\n"
                f"Tdp               = {d['room']['Tdp']:.2f} °F\n")
            self.draw_chart()
        except Exception as e:
            messagebox.showerror("Cálculo V5.2",str(e))

    def calculate_bypass(self):
        try:
            d = supply_from_room_loads(
                float(self.tr.get()), float(self.rh.get()),
                float(self.qs.get()), float(self.ql.get()),
                float(self.ts.get()), float(self.alt.get())
            )
            m = mixed_air_state(
                float(self.toa.get()), float(self.rhoa.get()),
                float(self.tr.get()), float(self.rh.get()),
                float(self.oap.get())/100.0, float(self.alt.get())
            )
            self.mix_state = m
            self.last = d
            bf = coil_bypass_factor(
                m["T"], m["W"],
                d["T_supply_F"], d["W_supply"],
                d["ADP_F"], d["W_ADP"]
            )
            lines = [
                "",
                "BYPASS FACTOR DEL SERPENTÍN",
                f"Entrada serpentín M = {m['T']:.2f} °F",
                f"Salida serpentín S  = {d['T_supply_F']:.2f} °F",
                f"ADP                 = {d['ADP_F']:.2f} °F",
                f"BF por temperatura  = {bf['BF_T']:.4f} ({bf['BYPASS_PCT']:.2f} %)",
                ("BF por humedad      = N/A" if bf["BF_W"] is None
                 else f"BF por humedad      = {bf['BF_W']:.4f}"),
                f"CF                  = {bf['CF']:.4f} ({bf['CONTACT_PCT']:.2f} %)",
            ]
            if bf["delta_BF"] is not None:
                lines.append(f"Diferencia BF T-W   = {bf['delta_BF']:.4f}")
                if bf["delta_BF"] > 0.03:
                    lines.append("AVISO: BF_T y BF_W no coinciden bien; revise M, S o ADP.")
            self.result.insert("end", "\n".join(lines) + "\n")
            self.draw_chart()
        except Exception as e:
            messagebox.showerror("Bypass Factor", str(e))

    def calculate_mix(self):
        try:
            m=mixed_air_state(float(self.toa.get()),float(self.rhoa.get()),
                              float(self.tr.get()),float(self.rh.get()),
                              float(self.oap.get())/100.0,float(self.alt.get()))
            self.mix_state=m
            self.result.insert("end",
                f"\nMEZCLA OA + RA\n"
                f"T mezcla         = {m['T']:.2f} °F\n"
                f"HR mezcla        = {m['RH']:.2f} %\n"
                f"W mezcla         = {m['Wgr']:.2f} grains/lb\n"
                f"h mezcla         = {m['h']:.2f} BTU/lb\n")
            self.draw_chart()
        except Exception as e:
            messagebox.showerror("Mezcla de aire",str(e))

if __name__ == "__main__":
    App().mainloop()
