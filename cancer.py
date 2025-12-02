import serial
from subprocess import run
from time import sleep
from threading import Lock, Thread

mutex = Lock()

# Logs = último valor que nosotros mandamos al sistema
volumen_log: int = 0
brillo_log: int = 0

# Sys = último valor que leímos DEL sistema
volumen_sys: int = 0
brillo_sys: int = 0

# --- API de volumen con PowerShell / C# embebido ---
api_volumen = r"""
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume
{
    int SetMasterVolumeLevelScalar(float fLevel, Guid pguidEventContext);
    int GetMasterVolumeLevelScalar(out float pfLevel);
    int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, Guid pguidEventContext);
    int GetMute(out bool pbMute);

    int RegisterControlChangeNotify(IAudioEndpointVolumeCallback pNotify);
    int UnregisterControlChangeNotify(IAudioEndpointVolumeCallback pNotify);
}

[Guid("657804FA-D6AD-4496-8A60-352752AF4F89"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolumeCallback
{
    int OnNotify(IntPtr pNotifyData);
}

[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice
{
    int Activate(ref Guid id, int clsCtx, int activationParams, out IAudioEndpointVolume aev);
}

[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator
{
    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice endpoint);
}

[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
class MMDeviceEnumeratorComObject { }

public class Audio
{
    static IAudioEndpointVolume endpoint;

    static IAudioEndpointVolume Vol()
    {
        if (endpoint == null)
        {
            var enumerator = new MMDeviceEnumeratorComObject() as IMMDeviceEnumerator;
            IMMDevice dev = null;
            Marshal.ThrowExceptionForHR(
                enumerator.GetDefaultAudioEndpoint(0, 1, out dev));

            Guid epvid = typeof(IAudioEndpointVolume).GUID;
            Marshal.ThrowExceptionForHR(
                dev.Activate(ref epvid, 23, 0, out endpoint));
        }
        return endpoint;
    }

    public static float Volume
    {
        get { float v = -1; Marshal.ThrowExceptionForHR(Vol().GetMasterVolumeLevelScalar(out v)); return v; }
        set { Marshal.ThrowExceptionForHR(Vol().SetMasterVolumeLevelScalar(value, Guid.Empty)); }
    }
}
"@"""
# --- FIN api_volumen ---


def set_volumen(volumen: int) -> None:
    """Ajusta el volumen del sistema (0-100)"""
    global volumen_log, volumen_sys, api_volumen
    volumen = max(0, min(100, volumen))
    command = f"""
{api_volumen}

[audio]::Volume = {volumen / 100}
"""
    run(["powershell", "-Command", command])
    volumen_log = volumen
    volumen_sys = volumen  # mantenemos en sync nuestro registro del sistema


def get_volumen() -> int:
    """Obtiene el volumen del sistema en 0-100"""
    global api_volumen
    command = f"""
{api_volumen}

[int]([math]::Round([audio]::Volume * 100))
"""
    res = run(
        ["powershell", "-Command", command],
        capture_output=True,
        text=True
    )

    # Nos quedamos con la última línea no vacía
    out = res.stdout.strip().splitlines()
    if not out:
        print("get_volumen(): salida vacía, stdout/stderr:")
        print("STDOUT:", res.stdout)
        print("STDERR:", res.stderr)
        return 0

    last = out[-1].strip()
    try:
        return int(last)
    except ValueError:
        # Debug por si vuelve a fallar
        print("Error convirtiendo a int, stdout/stderr:")
        print("STDOUT:", res.stdout)
        print("STDERR:", res.stderr)
        return 0



def set_brillo(brillo: int) -> None:
    """Ajusta el brillo del sistema (0-100)"""
    global brillo_log, brillo_sys
    brillo = max(0, min(100, brillo))
    command = f"""
$WmiBrightness = Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods
$WmiBrightness.WmiSetBrightness(1, {brillo})
"""
    run(["powershell", "-Command", command])
    brillo_log = brillo
    brillo_sys = brillo


def get_brillo() -> int:
    """Obtiene el brillo actual (0-100)"""
    command = """
$WmiBrightness = Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness
$WmiBrightness.CurrentBrightness
"""
    res = run(["powershell", "-Command", command],
              capture_output=True, text=True)
    return int(res.stdout.strip())


def verificar_volumen():
    """Hilo que detecta cambios de volumen hechos desde Windows y los manda al Arduino."""
    global brillo_sys, volumen_sys
    while True:
        try:
            volumen = get_volumen()
            with mutex:
                if volumen_sys != volumen:
                    volumen_sys = volumen
                    # Mandar al Arduino "volumen,brillo\n"
                    ser.write(f"{volumen_sys},{brillo_sys}\n".encode())
        except Exception as e:
            print("Error en verificar_volumen:", e)
        sleep(1.0)  # no spammear PowerShell


def verificar_brillo():
    """Hilo que detecta cambios de brillo hechos desde Windows y los manda al Arduino."""
    global brillo_sys, volumen_sys
    while True:
        try:
            brillo = get_brillo()
            with mutex:
                if brillo_sys != brillo:
                    brillo_sys = brillo
                    ser.write(f"{volumen_sys},{brillo_sys}\n".encode())
        except Exception as e:
            print("Error en verificar_brillo:", e)
        sleep(1.0)


if __name__ == "__main__":
    # Ajusta este COM al que uses con com0com o con el Arduino real
    ser = serial.Serial("COM1", 9600)
    sleep(2)  # pequeña espera para que el Arduino reinicie

    # Leer estado inicial del sistema y mandarlo al Arduino
    volumen_sys = get_volumen()
    brillo_sys = get_brillo()
    volumen_log = volumen_sys
    brillo_log = brillo_sys

    ser.write(f"{volumen_sys},{brillo_sys}\n".encode())
    print(f"Estado inicial → Volumen: {volumen_sys} | Brillo: {brillo_sys}")

    # Lanzar hilos que vigilan cambios hechos desde Windows
    t_vol = Thread(target=verificar_volumen, daemon=True)
    t_bri = Thread(target=verificar_brillo, daemon=True)
    t_vol.start()
    t_bri.start()

    # Bucle principal: aplica cambios que vienen del Arduino
    while True:
        linea = ser.readline().decode().strip()

        if linea:
            try:
                volumen, brillo = map(int, linea.split(","))

                with mutex:
                    if volumen_log != volumen:
                        set_volumen(volumen)

                    if brillo_log != brillo:
                        set_brillo(brillo)

                print(f"Arduino → Volumen: {volumen} | Brillo: {brillo}")

            except ValueError:
                print("Datos inválidos:", linea)