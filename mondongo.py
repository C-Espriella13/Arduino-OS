import serial
from subprocess import run
from time import sleep
from threading import Lock, Thread
from ctypes import POINTER, cast
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

mutex = Lock()

volumen_log: int = 0; brillo_log: int = 0
volumen_sys: int = 0; brillo_sys: int = 0

_volume_iface = None

def _get_volume_iface():
    global _volume_iface
    if _volume_iface is None:
        speakers = AudioUtilities.GetSpeakers()
        interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        _volume_iface = cast(interface, POINTER(IAudioEndpointVolume))
    return _volume_iface

def set_volumen(volumen: int) -> None:
    "Mondongo API for volume control"
    global volumen_log
    iface = _get_volume_iface()
    iface.SetMasterVolumeLevelScalar(volumen / 100, None)
    volumen_log = volumen

def get_volumen() -> int:
    "Mondongo API for volume control"
    iface = _get_volume_iface()
    volumen = iface.GetMasterVolumeLevelScalar()
    return int(volumen * 100)

def set_brillo(brillo: int) -> None:
    global brillo_log
    command: str = f"""
$WmiBrightness = (Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods)
$WmiBrightness.WmiSetBrightness(1, {brillo})
"""
    run(["powershell", "-Command", command])
    brillo_log = brillo

def get_brillo() -> int:
    command: str = """
Register-WmiEvent -Namespace root/WMI -Class WmiMonitorBrightnessEvent -SourceIdentifier BrilloCambio | Out-Null
Wait-Event -SourceIdentifier BrilloCambio | Out-Null
$WmiBrightness = (Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness)
$WmiBrightness.CurrentBrightness
Unregister-Event -SourceIdentifier BrilloCambio | Out-Null
Remove-Event -SourceIdentifier BrilloCambio | Out-Null
"""
    brillo_res = run(["powershell", "-Command", command], capture_output=True, text=True)
    return int(brillo_res.stdout)

def verificar_volumen():
    global brillo_sys, volumen_sys
    while True:
        volumen = get_volumen()
        with mutex:
            if (volumen_sys != volumen):
                ser.writelines([f"{volumen},{brillo_sys}".encode()])
                volumen_sys = volumen

def verificar_brillo():
    global brillo_sys, volumen_sys
    while True:
        brillo = get_brillo()
        with mutex:
            if (brillo_sys != brillo):
                ser.writelines([f"{volumen_sys},{brillo}".encode()])
                brillo_sys = brillo

if __name__ == "__main__":
    ser = serial.Serial("COM1", 9600)
    sleep(2)

    t_vol = Thread(target=verificar_volumen)
    t_bri = Thread(target=verificar_brillo)
    t_vol.start()
    t_bri.start()

    while True:
        linea = ser.readline().decode().strip()

        if linea:
            try:
                volumen, brillo = map(int, linea.split(","))

                if (volumen_log == volumen and brillo_log == brillo):
                    continue

                if (volumen_log != volumen):
                    set_volumen(volumen)
                if (brillo_log != brillo):
                    set_brillo(brillo)

                print(f"Volumen: {volumen} | Brillo: {brillo}", "\n")

            except ValueError:
                print("Datos inválidos:", linea)
