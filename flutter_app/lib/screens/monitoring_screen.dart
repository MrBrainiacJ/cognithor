import 'dart:async';

import 'package:flutter/material.dart';
import 'package:cognithor_ui/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';

import 'package:cognithor_ui/providers/connection_provider.dart';
import 'package:cognithor_ui/theme/jarvis_theme.dart';
import 'package:cognithor_ui/widgets/neon_card.dart';
import 'package:cognithor_ui/widgets/jarvis_empty_state.dart';
import 'package:cognithor_ui/widgets/jarvis_section.dart';
import 'package:cognithor_ui/widgets/jarvis_stat.dart';
import 'package:cognithor_ui/widgets/jarvis_status_badge.dart';
import 'package:cognithor_ui/widgets/monitoring/live_logs_tab.dart';

class MonitoringScreen extends StatefulWidget {
  const MonitoringScreen({super.key});

  @override
  State<MonitoringScreen> createState() => _MonitoringScreenState();
}

class _MonitoringScreenState extends State<MonitoringScreen> {
  Map<String, dynamic>? _dashboard;
  List<dynamic>? _events;
  bool _loading = true;
  String? _error;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _loadData();
    _refreshTimer = Timer.periodic(
      const Duration(seconds: 10),
      (_) => _loadData(),
    );
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadData() async {
    try {
      final api = context.read<ConnectionProvider>().api;
      final results = await Future.wait([
        api.getMonitoringDashboard(),
        api.getMonitoringEvents(n: 50),
      ]);

      final dashboard = results[0];
      final eventsResult = results[1];

      if (!mounted) return;

      if (dashboard.containsKey('error')) {
        setState(() {
          _error = dashboard['error'] as String;
          _loading = false;
        });
        return;
      }

      setState(() {
        _dashboard = dashboard;
        _events = eventsResult['events'] as List<dynamic>? ?? [];
        _loading = false;
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);

    if (_loading) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 16),
            Text(l.loading),
          ],
        ),
      );
    }

    if (_error != null && _dashboard == null) {
      return JarvisEmptyState(
        icon: Icons.monitor_heart_outlined,
        title: l.noData,
        subtitle: _error,
        action: ElevatedButton.icon(
          onPressed: _loadData,
          icon: const Icon(Icons.refresh),
          label: Text(l.retry),
        ),
      );
    }

    return DefaultTabController(
      length: 3,
      child: Column(
        children: [
          Material(
            color: Colors.transparent,
            child: TabBar(
              indicatorColor: JarvisTheme.accent,
              labelColor: JarvisTheme.accent,
              unselectedLabelColor: JarvisTheme.textSecondary,
              tabs: const [
                Tab(
                  icon: Icon(Icons.dashboard_outlined),
                  text: 'Dashboard',
                ),
                Tab(
                  icon: Icon(Icons.event_note_outlined),
                  text: 'Events',
                ),
                Tab(
                  icon: Icon(Icons.terminal_outlined),
                  text: 'Live Logs',
                ),
              ],
            ),
          ),
          Expanded(
            child: TabBarView(
              children: [
                _DashboardTab(
                  dashboard: _dashboard!,
                  onRefresh: _loadData,
                ),
                _EventsTab(
                  events: _events,
                  onRefresh: _loadData,
                ),
                const LiveLogsTab(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Dashboard Tab ────────────────────────────────────────────────────

class _DashboardTab extends StatelessWidget {
  const _DashboardTab({
    required this.dashboard,
    required this.onRefresh,
  });

  final Map<String, dynamic> dashboard;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final uptime = dashboard['uptime']?.toString() ?? '-';
    final activeSessions = dashboard['active_sessions']?.toString() ?? '0';
    final totalRequests = dashboard['total_requests']?.toString() ?? '0';

    return RefreshIndicator(
      onRefresh: onRefresh,
      color: JarvisTheme.accent,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              JarvisStat(
                label: l.uptime,
                value: uptime,
                icon: Icons.timer,
                color: JarvisTheme.green,
              ),
              JarvisStat(
                label: l.activeSessions,
                value: activeSessions,
                icon: Icons.people,
                color: JarvisTheme.accent,
              ),
              JarvisStat(
                label: l.totalRequests,
                value: totalRequests,
                icon: Icons.trending_up,
                color: JarvisTheme.orange,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ── Events Tab ───────────────────────────────────────────────────────

class _EventsTab extends StatelessWidget {
  const _EventsTab({
    required this.events,
    required this.onRefresh,
  });

  final List<dynamic>? events;
  final Future<void> Function() onRefresh;

  Color _severityColor(String severity) {
    return switch (severity.toUpperCase()) {
      'ERROR' || 'CRITICAL' => JarvisTheme.red,
      'WARNING' || 'WARN' => JarvisTheme.orange,
      'INFO' => JarvisTheme.accent,
      _ => JarvisTheme.green,
    };
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);

    return RefreshIndicator(
      onRefresh: onRefresh,
      color: JarvisTheme.accent,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          JarvisSection(
            title: l.events,
            trailing: Text(
              l.refreshing,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          if (events == null || events!.isEmpty)
            NeonCard(
              tint: JarvisTheme.sectionAdmin,
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Text(
                    l.noEvents,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
              ),
            )
          else
            ...events!.map<Widget>((event) {
              final e = event as Map<String, dynamic>;
              final severity = e['severity']?.toString() ?? 'INFO';
              final message = e['message']?.toString() ?? '';
              final timestamp = e['timestamp']?.toString() ?? '';

              return NeonCard(
                tint: JarvisTheme.sectionAdmin,
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 10,
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    JarvisStatusBadge(
                      label: severity,
                      color: _severityColor(severity),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            message,
                            style: Theme.of(context).textTheme.bodyMedium,
                          ),
                          if (timestamp.isNotEmpty)
                            Text(
                              timestamp,
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }
}
