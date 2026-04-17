using System;
using System.Diagnostics;
using System.Drawing;
using System.Reflection;
using System.Windows.Forms;

namespace Cognithor;

sealed class AppShell : IDisposable
{
    readonly ProcessManager _processes;
    readonly HealthChecker _health;
    readonly NotifyIcon _trayIcon;
    readonly ToolStripMenuItem _statusItem;

    static readonly string Version = typeof(AppShell).Assembly
        .GetCustomAttribute<System.Reflection.AssemblyInformationalVersionAttribute>()
        ?.InformationalVersion ?? "dev";

    public AppShell(string[] args)
    {
        _processes = new ProcessManager();
        _health = new HealthChecker();

        var openItem = new ToolStripMenuItem("Open Command Center");
        openItem.Click += (_, _) => OpenBrowser();
        openItem.Font = new Font(openItem.Font, FontStyle.Bold);

        _statusItem = new ToolStripMenuItem("Status: Starting...") { Enabled = false };

        var restartItem = new ToolStripMenuItem("Restart Backend");
        restartItem.Click += (_, _) =>
        {
            SetStatus(AppStatus.Starting);
            _processes.RestartBackend();
        };

        var quitItem = new ToolStripMenuItem("Quit Cognithor");
        quitItem.Click += (_, _) => Shutdown();

        var versionItem = new ToolStripMenuItem($"v{Version}") { Enabled = false };

        var menu = new ContextMenuStrip();
        menu.Items.Add(openItem);
        menu.Items.Add(_statusItem);
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add(restartItem);
        menu.Items.Add(quitItem);
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add(versionItem);

        _trayIcon = new NotifyIcon
        {
            Icon = LoadIcon(),
            Text = "Cognithor - Starting...",
            ContextMenuStrip = menu,
            Visible = true,
        };
        _trayIcon.DoubleClick += (_, _) => OpenBrowser();

        _health.StatusChanged += (prev, next) =>
        {
            SetStatus(next);
            if (next == AppStatus.Stopped && prev != AppStatus.Starting)
            {
                _trayIcon.ShowBalloonTip(5000, "Cognithor",
                    "Backend has stopped. Right-click to restart.",
                    ToolTipIcon.Error);
            }
        };

        _processes.StartAll();
        _health.Start();
    }

    void SetStatus(AppStatus status)
    {
        var (text, label) = status switch
        {
            AppStatus.Starting  => ("Cognithor - Starting...",     "Status: Starting..."),
            AppStatus.Healthy   => ("Cognithor - Running",         "Status: Running"),
            AppStatus.Unhealthy => ("Cognithor - Backend error",   "Status: Error"),
            AppStatus.Stopped   => ("Cognithor - Backend stopped", "Status: Stopped"),
            _ => ("Cognithor", "Status: Unknown"),
        };
        _trayIcon.Text = text;
        _statusItem.Text = label;
    }

    static Icon LoadIcon()
    {
        var path = System.IO.Path.Combine(AppContext.BaseDirectory, "Resources", "app_icon.ico");
        if (System.IO.File.Exists(path))
            return new Icon(path);
        return SystemIcons.Application;
    }

    static void OpenBrowser()
    {
        Process.Start(new ProcessStartInfo
        {
            FileName = "http://localhost:8741",
            UseShellExecute = true,
        });
    }

    void Shutdown()
    {
        _health.Stop();
        _processes.KillAll();
        _trayIcon.Visible = false;
        Application.Exit();
    }

    public void Dispose()
    {
        _health.Dispose();
        _processes.Dispose();
        _trayIcon.Dispose();
    }
}
