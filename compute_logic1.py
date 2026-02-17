# -*- coding: utf-8 -*-
"""
Created on Tue Feb 17 14:56:14 2026

@author: Adwait
"""

from pymavlink import mavutil
import numpy as np


def analyze_log(logfile):
    mav = mavutil.mavlink_connection(logfile)

    imu_g = []
    motor_outputs = []
    thr_out = []
    th_limit = []
    bat_volt = []
    vcc = []
    mcu_temp = []
    hover_throttle = []

    while True:
        msg = mav.recv_match(blocking=False)
        if msg is None:
            break

        t = msg.get_type()

        if t == "IMU":
            gmag = np.sqrt(msg.GyrX**2 + msg.GyrY**2 + msg.GyrZ**2)
            imu_g.append(gmag)

        elif t == "RCOU":
            motor_outputs.append([msg.C1, msg.C2, msg.C3, msg.C4])

        elif t == "MOTB":
            thr_out.append(msg.ThrOut)
            if hasattr(msg, "ThLimit"):
                th_limit.append(msg.ThLimit)

        elif t == "BAT":
            bat_volt.append(msg.Volt)

        elif t == "POWR":
            if hasattr(msg, "Vcc"):
                vcc.append(msg.Vcc)

        elif t == "MCU":
            if hasattr(msg, "MTemp"):
                mcu_temp.append(msg.MTemp)

        elif t == "CTUN":
            if hasattr(msg, "ThH"):
                hover_throttle.append(msg.ThH)

    # convert arrays
    imu_g = np.array(imu_g)
    motor_outputs = np.array(motor_outputs)

    metrics = {
        "gyro_rms": np.sqrt(np.mean(imu_g**2)) if len(imu_g) else np.nan,
        "motor_imbalance": np.std(motor_outputs) if len(motor_outputs) else np.nan,
        "th_limit_max": np.max(th_limit) if len(th_limit) else np.nan,
        "bat_volt_min": np.min(bat_volt) if len(bat_volt) else np.nan,
        "bat_volt_mean": np.mean(bat_volt) if len(bat_volt) else np.nan,
        "vcc_min": np.min(vcc) if len(vcc) else np.nan,
        "mcu_temp_mean": np.mean(mcu_temp) if len(mcu_temp) else np.nan,
        "hover_throttle": np.mean(hover_throttle) if len(hover_throttle) else np.nan,
    }

    series = {
        "thrust": th_limit,
        "battery": bat_volt,
        "vcc": vcc,
        "vibration": imu_g,
        "motors": motor_outputs,
    }

    return metrics, series

def assess_subsystems(metrics):
    subsystems = {}

    # Thrust
    th = metrics["th_limit_max"]
    if th >= 0.95:
        subsystems["thrust"] = {
            "health": 0.3,
            "issues": ["Sustained thrust saturation"],
            "interp": "Drone operating near thrust limit",
            "rec": "Reduce payload or increase propulsion thrust",
        }
    elif th >= 0.8:
        subsystems["thrust"] = {
            "health": 0.6,
            "issues": ["High thrust usage"],
            "interp": "Limited thrust margin",
            "rec": "Monitor payload and mission profile",
        }
    else:
        subsystems["thrust"] = {
            "health": 1.0,
            "issues": [],
            "interp": "Adequate thrust margin",
            "rec": "No action required",
        }

    # Battery
    v = metrics["bat_volt_mean"]
    if v < 20:
        subsystems["battery"] = {
            "health": 0.4,
            "issues": ["Low battery voltage"],
            "interp": "Significant voltage sag",
            "rec": "Replace or inspect battery",
        }
    else:
        subsystems["battery"] = {
            "health": 1.0,
            "issues": [],
            "interp": "Normal discharge profile",
            "rec": "Battery healthy",
        }

    # FC Power
    vcc = metrics["vcc_min"]
    if vcc < 4.8:
        subsystems["fc"] = {
            "health": 0.3,
            "issues": ["FC voltage instability"],
            "interp": "Risk of brownout",
            "rec": "Check power module and wiring",
        }
    else:
        subsystems["fc"] = {
            "health": 1.0,
            "issues": [],
            "interp": "Stable FC supply",
            "rec": "No action required",
        }

    # Propulsion vibration
    vib = metrics["gyro_rms"]
    if vib > 0.4:
        subsystems["propulsion"] = {
            "health": 0.4,
            "issues": ["High vibration"],
            "interp": "Propulsion imbalance",
            "rec": "Balance props and inspect motors",
        }
    else:
        subsystems["propulsion"] = {
            "health": 1.0,
            "issues": [],
            "interp": "Low vibration levels",
            "rec": "Propulsion healthy",
        }

    # Motor balance
    mb = metrics["motor_imbalance"]
    if mb > 80:
        subsystems["motor"] = {
            "health": 0.4,
            "issues": ["Motor imbalance"],
            "interp": "Uneven thrust distribution",
            "rec": "Inspect motors and frame alignment",
        }
    else:
        subsystems["motor"] = {
            "health": 1.0,
            "issues": [],
            "interp": "Balanced motor outputs",
            "rec": "No action required",
        }

    # Efficiency
    ht = metrics["hover_throttle"]
    if ht > 0.45:
        subsystems["efficiency"] = {
            "health": 0.4,
            "issues": ["Low thrust efficiency"],
            "interp": "High hover throttle",
            "rec": "Increase prop size or motor thrust",
        }
    else:
        subsystems["efficiency"] = {
            "health": 1.0,
            "issues": [],
            "interp": "High thrust reserve",
            "rec": "Propulsion sizing adequate",
        }

    # Thermal
    temp = metrics["mcu_temp_mean"]
    if temp > 75:
        subsystems["thermal"] = {
            "health": 0.4,
            "issues": ["High MCU temperature"],
            "interp": "Thermal stress risk",
            "rec": "Improve cooling or airflow",
        }
    else:
        subsystems["thermal"] = {
            "health": 1.0,
            "issues": [],
            "interp": "Normal FC temperature",
            "rec": "No action required",
        }

    return subsystems

def overall_bottleneck(subsystems):
    worst = min(subsystems.items(), key=lambda x: x[1]["health"])
    name, data = worst
    return name, data["rec"]