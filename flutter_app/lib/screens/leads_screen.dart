import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:cognithor_ui/data/known_packs.dart';
import 'package:cognithor_ui/l10n/generated/app_localizations.dart';
import 'package:cognithor_ui/providers/connection_provider.dart';
import 'package:cognithor_ui/providers/reddit_leads_provider.dart';
import 'package:cognithor_ui/providers/sources_provider.dart';
import 'package:cognithor_ui/theme/jarvis_theme.dart';
import 'package:cognithor_ui/widgets/jarvis_empty_state.dart';
import 'package:cognithor_ui/widgets/jarvis_stat.dart';
import 'package:cognithor_ui/widgets/leads/lead_card.dart';
import 'package:cognithor_ui/widgets/leads/lead_detail_sheet.dart';
import 'package:cognithor_ui/widgets/leads/lead_wizard.dart';
import 'package:cognithor_ui/widgets/packs/locked_pack_card.dart';

class LeadsScreen extends StatefulWidget {
  const LeadsScreen({super.key});

  @override
  State<LeadsScreen> createState() => _LeadsScreenState();
}

class _LeadsScreenState extends State<LeadsScreen> {
  bool _initialized = false;
  String? _activeSourceFilter;

  // Source chips shown in the filter bar (sourceId -> display label)
  static const List<(String, String)> _sourceChips = [
    ('', 'All'),
    ('reddit', 'Reddit'),
    ('hn', 'HN'),
    ('discord', 'Discord'),
    ('rss', 'RSS'),
  ];

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

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<SourcesProvider>().refresh();
    });
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
      MaterialPageRoute<void>(builder: (_) => LeadWizard(leads: newLeads)),
    ).then((_) => provider.fetchLeads());
  }

  void _archiveLead(String id) {
    context.read<RedditLeadsProvider>().updateLead(id, status: 'archived');
  }

  void _replyLead(String id) {
    context.read<RedditLeadsProvider>().replyToLead(id);
  }

  Widget _buildUpsellSection(SourcesProvider sources) {
    final installed = sources.sources.map((s) => s.sourceId).toSet();
    final lockedPacks = kKnownPacks.where((p) => !installed.contains(p.sourceId)).toList();
    if (lockedPacks.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Text(
            'More sources available',
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
        ...lockedPacks.map(
          (p) => Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: LockedPackCard(pack: p),
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final sources = context.watch<SourcesProvider>();

    return Consumer<RedditLeadsProvider>(
      builder: (context, provider, _) {
        return Scaffold(
          body: Column(
            children: [
              // Stats bar
              _StatsBar(provider: provider, onProcessQueue: _openWizard),
              // Source filter chips
              _SourceFilterBar(
                sourceChips: _sourceChips,
                activeFilter: _activeSourceFilter,
                onFilterChanged: (v) => setState(() => _activeSourceFilter = v),
              ),
              // Status filter row
              _FilterRow(provider: provider),
              // Upsell section + lead list
              Expanded(
                child: provider.loading && provider.leads.isEmpty
                    ? const Center(child: CircularProgressIndicator())
                    : RefreshIndicator(
                        onRefresh: () async {
                          await Future.wait([
                            provider.fetchLeads(),
                            sources.refresh(),
                          ]);
                        },
                        child: ListView(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 8,
                          ),
                          children: [
                            _buildUpsellSection(sources),
                            if (provider.leads.isEmpty)
                              JarvisEmptyState(
                                icon: Icons.track_changes,
                                title: l.noLeadsFound,
                                subtitle: l.noLeadsHint,
                              )
                            else
                              ...provider.leads.map(
                                (lead) => LeadCard(
                                  lead: lead,
                                  onTap: () => _openDetail(lead),
                                  onReply: () => _replyLead(lead.id),
                                  onArchive: () => _archiveLead(lead.id),
                                ),
                              ),
                          ],
                        ),
                      ),
              ),
            ],
          ),
          floatingActionButton: FloatingActionButton.extended(
            onPressed: provider.scanning ? null : _scanNow,
            icon: provider.scanning
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.radar),
            label: Text(provider.scanning ? l.scanning : l.scanNow),
            backgroundColor: JarvisTheme.accent,
          ),
        );
      },
    );
  }
}

// ---------------------------------------------------------------------------

class _SourceFilterBar extends StatelessWidget {
  const _SourceFilterBar({
    required this.sourceChips,
    required this.activeFilter,
    required this.onFilterChanged,
  });

  final List<(String, String)> sourceChips;
  final String? activeFilter;
  final ValueChanged<String?> onFilterChanged;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 44,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        children: [
          for (final (id, label) in sourceChips) ...[
            ChoiceChip(
              label: Text(label),
              selected: (activeFilter ?? '') == id,
              onSelected: (_) => onFilterChanged(id.isEmpty ? null : id),
              visualDensity: VisualDensity.compact,
            ),
            const SizedBox(width: 8),
          ],
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------

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
