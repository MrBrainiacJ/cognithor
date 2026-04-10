import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:cognithor_ui/l10n/generated/app_localizations.dart';
import 'package:cognithor_ui/providers/connection_provider.dart';
import 'package:cognithor_ui/providers/reddit_leads_provider.dart';
import 'package:cognithor_ui/theme/jarvis_theme.dart';
import 'package:cognithor_ui/widgets/jarvis_empty_state.dart';
import 'package:cognithor_ui/widgets/jarvis_stat.dart';
import 'package:cognithor_ui/widgets/leads/lead_card.dart';
import 'package:cognithor_ui/widgets/leads/lead_detail_sheet.dart';
import 'package:cognithor_ui/widgets/leads/lead_wizard.dart';

class RedditLeadsScreen extends StatefulWidget {
  const RedditLeadsScreen({super.key});

  @override
  State<RedditLeadsScreen> createState() => _RedditLeadsScreenState();
}

class _RedditLeadsScreenState extends State<RedditLeadsScreen> {
  bool _initialized = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_initialized) {
      _initialized = true;
      final conn = context.read<ConnectionProvider>();
      if (conn.state == JarvisConnectionState.connected) {
        context.read<RedditLeadsProvider>().init(conn.api);
      }
    }
  }

  void _openDetail(RedditLead lead) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => LeadDetailSheet(lead: lead),
    );
  }

  Future<void> _scanNow() async {
    await context.read<RedditLeadsProvider>().scanNow();
  }

  void _openWizard() {
    final provider = context.read<RedditLeadsProvider>();
    final newLeads = provider.leads.where((l) => l.status == 'new').toList()
      ..sort((a, b) => b.intentScore.compareTo(a.intentScore));
    if (newLeads.isEmpty) return;
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => LeadWizard(leads: newLeads)),
    ).then((_) => provider.fetchLeads());
  }

  void _archiveLead(String id) {
    context.read<RedditLeadsProvider>().updateLead(id, status: 'archived');
  }

  void _replyLead(String id) {
    context.read<RedditLeadsProvider>().replyToLead(id);
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);

    return Consumer<RedditLeadsProvider>(
      builder: (context, provider, _) {
        return Scaffold(
          body: Column(
            children: [
              // Stats bar
              _StatsBar(provider: provider, onProcessQueue: _openWizard),
              // Filter row
              _FilterRow(provider: provider),
              // Lead list
              Expanded(
                child: provider.loading && provider.leads.isEmpty
                    ? const Center(child: CircularProgressIndicator())
                    : provider.leads.isEmpty
                        ? JarvisEmptyState(
                            icon: Icons.track_changes,
                            title: l.noLeadsFound,
                            subtitle: l.noLeadsHint,
                          )
                        : RefreshIndicator(
                            onRefresh: () => provider.fetchLeads(),
                            child: ListView.builder(
                              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                              itemCount: provider.leads.length,
                              itemBuilder: (context, i) {
                                final lead = provider.leads[i];
                                return LeadCard(
                                  lead: lead,
                                  onTap: () => _openDetail(lead),
                                  onReply: () => _replyLead(lead.id),
                                  onArchive: () => _archiveLead(lead.id),
                                );
                              },
                            ),
                          ),
              ),
            ],
          ),
          floatingActionButton: FloatingActionButton.extended(
            onPressed: provider.scanning ? null : _scanNow,
            icon: provider.scanning
                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.radar),
            label: Text(provider.scanning ? l.scanning : l.scanNow),
            backgroundColor: JarvisTheme.accent,
          ),
        );
      },
    );
  }
}

class _StatsBar extends StatelessWidget {
  const _StatsBar({required this.provider, this.onProcessQueue});
  final RedditLeadsProvider provider;
  final VoidCallback? onProcessQueue;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Wrap(
        spacing: 12,
        runSpacing: 8,
        children: [
          JarvisStat(
            label: 'New',
            value: '${provider.newCount}',
            icon: Icons.fiber_new,
            color: JarvisTheme.accent,
          ),
          JarvisStat(
            label: 'Reviewed',
            value: '${provider.reviewedCount}',
            icon: Icons.check_circle_outline,
            color: Colors.orange,
          ),
          JarvisStat(
            label: 'Replied',
            value: '${provider.repliedCount}',
            icon: Icons.reply,
            color: JarvisTheme.green,
          ),
          if (provider.newCount > 0 && onProcessQueue != null)
            ElevatedButton.icon(
              onPressed: onProcessQueue,
              icon: const Icon(Icons.playlist_play, size: 18),
              label: Text(l.processQueue),
              style: ElevatedButton.styleFrom(backgroundColor: JarvisTheme.accent),
            ),
        ],
      ),
    );
  }
}

class _FilterRow extends StatelessWidget {
  const _FilterRow({required this.provider});
  final RedditLeadsProvider provider;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        children: [
          SegmentedButton<String>(
            segments: [
              ButtonSegment(value: '', label: Text(l.filterAll)),
              ButtonSegment(value: 'new', label: Text(l.leadNew)),
              ButtonSegment(value: 'reviewed', label: Text(l.leadReviewed)),
              ButtonSegment(value: 'replied', label: Text(l.leadReplied)),
            ],
            selected: {provider.statusFilter},
            onSelectionChanged: (s) => provider.setStatusFilter(s.first),
            style: ButtonStyle(
              visualDensity: VisualDensity.compact,
              textStyle: WidgetStatePropertyAll(
                Theme.of(context).textTheme.labelSmall,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
