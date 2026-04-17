using System;
using System.Threading;
using System.Windows.Forms;

namespace Cognithor;

static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        using var mutex = new Mutex(true, @"Global\CognithorAppShell", out bool created);
        if (!created)
        {
            MessageBox.Show("Cognithor is already running.\nCheck the system tray.",
                "Cognithor", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        Application.EnableVisualStyles();
        Application.SetHighDpiMode(HighDpiMode.PerMonitorV2);
        Application.SetCompatibleTextRenderingDefault(false);

        using var shell = new AppShell(args);
        Application.Run();
    }
}
