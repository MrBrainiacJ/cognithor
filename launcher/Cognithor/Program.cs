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
            MessageBox.Show("Cognithor is already running.", "Cognithor",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        Application.EnableVisualStyles();
        Application.SetHighDpiMode(HighDpiMode.PerMonitorV2);
        Application.SetCompatibleTextRenderingDefault(false);

        var icon = new NotifyIcon
        {
            Icon = new System.Drawing.Icon(
                System.IO.Path.Combine(AppContext.BaseDirectory, "Resources", "app_icon.ico")),
            Text = "Cognithor - Starting...",
            Visible = true,
        };
        icon.DoubleClick += (_, _) => MessageBox.Show("Cognithor is running.");

        var menu = new ContextMenuStrip();
        menu.Items.Add("Quit", null, (_, _) => { icon.Visible = false; Application.Exit(); });
        icon.ContextMenuStrip = menu;

        Application.ApplicationExit += (_, _) => { icon.Visible = false; icon.Dispose(); };
        Application.Run();
    }
}
