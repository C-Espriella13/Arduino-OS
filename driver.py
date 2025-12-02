import serial
from subprocess import run
from time import sleep
from threading import Lock, Thread

mutex = Lock()

volumen_log: int = 0; brillo_log: int = 0
volumen_sys: int = 0; brillo_sys: int = 0

api_volumen = r"""
# Source - https://stackoverflow.com/a
# Posted by Vimes
# Retrieved 2025-12-02, License - CC BY-SA 3.0

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

public class VolumeCallback : IAudioEndpointVolumeCallback
{
    public int OnNotify(IntPtr pNotifyData)
    {
        float newVolume = Marshal.PtrToStructure<float>(IntPtr.Add(pNotifyData, 8));
        System.Management.Automation.PowerShell.Create()
            .AddCommand("New-Event")
            .AddParameter("SourceIdentifier", "VolumeChanged")
            .AddParameter("EventArguments", newVolume)
            .Invoke();
        return 0;
    }
}

public class Audio
{
    static IAudioEndpointVolume endpoint;
    static VolumeCallback callback;

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

            callback = new VolumeCallback();
            Marshal.ThrowExceptionForHR(endpoint.RegisterControlChangeNotify(callback));
        }
        return endpoint;
    }

    public static float Volume
    {
        get { float v = -1; Marshal.ThrowExceptionForHR(Vol().GetMasterVolumeLevelScalar(out v)); return v; }
        set { Marshal.ThrowExceptionForHR(Vol().SetMasterVolumeLevelScalar(value, Guid.Empty)); }
    }

    public static bool Mute
    {
        get { bool mute; Marshal.ThrowExceptionForHR(Vol().GetMute(out mute)); return mute; }
        set { Marshal.ThrowExceptionForHR(Vol().SetMute(value, Guid.Empty)); }
    }
}
"@"""

def set_volumen(volumen: int) -> None:
    global volumen_log, api_volumen
    command: str = f"""
{api_volumen}

[audio]::Volume = {volumen / 100}
"""
    run(["powershell", "-Command", command])
    volumen_log = volumen

def get_volumen() -> int:
    global api_volumen
    command: str = f"""
{api_volumen}

[audio]::Volume
"""
    volumen_res = run(["powershell", "-Command", command], capture_output=True, text=True)
    print(volumen_res.stdout)
    return int(float(volumen_res.stdout) * 100)

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

    # t_vol = Thread(target=verificar_volumen)
    t_bri = Thread(target=verificar_brillo)
    # t_vol.start()
    t_bri.start()

    while True:
        linea = ser.readline().decode().strip()

        if linea:
            try:
                volumen, brillo = map(int, linea.split(","))

                if (volumen_log == volumen and brillo_log == brillo):
                    continue

                # if (volumen_log != volumen):
                #     set_volumen(volumen)
                if (brillo_log != brillo):
                    set_brillo(brillo)

                print(f"Volumen: {volumen} | Brillo: {brillo}", "\n")

            except ValueError:
                print("Datos inválidos:", linea)
