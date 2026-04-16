/// Hardcoded pack catalog for the Flutter Command Center.
///
/// Used to render locked upsell cards for packs the user hasn't installed.
/// The live pricing is always on cognithor.com — this catalog is
/// stale-tolerant because the CTA button always opens the browser.
library;

import 'package:flutter/material.dart';

class KnownPack {
  final String qualifiedId;
  final String packId;
  final String displayName;
  final String tagline;
  final List<String> featureBullets;
  final String priceBadge;
  final String? listPriceBadge;
  final String packDetailUrl;
  final IconData icon;
  final Color accentColor;
  final String sourceId;

  const KnownPack({
    required this.qualifiedId,
    required this.packId,
    required this.displayName,
    required this.tagline,
    required this.featureBullets,
    required this.priceBadge,
    this.listPriceBadge,
    required this.packDetailUrl,
    required this.icon,
    required this.accentColor,
    required this.sourceId,
  });
}

const List<KnownPack> kKnownPacks = [
  KnownPack(
    qualifiedId: 'cognithor-official/reddit-lead-hunter-pro',
    packId: 'reddit-lead-hunter-pro',
    displayName: 'Reddit Lead Hunter Pro',
    tagline: 'Find high-intent leads on Reddit, score them with your local LLM, '
        'draft replies from 50 curated templates, and drop them into an encrypted CRM.',
    featureBullets: [
      'OAuth Reddit API (rate-safe, never banned)',
      '50 curated reply templates + style learner',
      'Playwright auto-poster + Telegram/Slack alerts',
    ],
    priceBadge: 'from \$79',
    listPriceBadge: '\$149',
    packDetailUrl: 'https://cognithor.com/packs/reddit-lead-hunter-pro',
    icon: Icons.forum,
    accentColor: Color(0xFFFF4500),
    sourceId: 'reddit',
  ),
  KnownPack(
    qualifiedId: 'cognithor-official/hn-lead-hunter',
    packId: 'hn-lead-hunter',
    displayName: 'Hacker News Lead Hunter',
    tagline: 'Monitor HN top/new/best with local LLM scoring. Free, bundled.',
    featureBullets: [
      'Official HN Firebase + Algolia APIs',
      'Local LLM scoring with your own model',
      'Ships with Cognithor Core',
    ],
    priceBadge: 'free',
    packDetailUrl: 'https://cognithor.com/packs/hn-lead-hunter',
    icon: Icons.article,
    accentColor: Color(0xFFFF6600),
    sourceId: 'hn',
  ),
  KnownPack(
    qualifiedId: 'cognithor-official/discord-lead-hunter',
    packId: 'discord-lead-hunter',
    displayName: 'Discord Lead Hunter',
    tagline: 'Score messages in your Discord channels. Requires your own bot token.',
    featureBullets: [
      'Bring your own Discord bot token',
      'Local LLM scoring',
      'Ships with Cognithor Core',
    ],
    priceBadge: 'free',
    packDetailUrl: 'https://cognithor.com/packs/discord-lead-hunter',
    icon: Icons.tag,
    accentColor: Color(0xFF5865F2),
    sourceId: 'discord',
  ),
  KnownPack(
    qualifiedId: 'cognithor-official/rss-lead-hunter',
    packId: 'rss-lead-hunter',
    displayName: 'RSS Lead Hunter',
    tagline: 'Score any RSS/Atom feed with your local LLM.',
    featureBullets: [
      'Stdlib XML parser',
      'RSS 2.0 + Atom support',
      'Ships with Cognithor Core',
    ],
    priceBadge: 'free',
    packDetailUrl: 'https://cognithor.com/packs/rss-lead-hunter',
    icon: Icons.rss_feed,
    accentColor: Color(0xFFFFA500),
    sourceId: 'rss',
  ),
];

KnownPack? findKnownPackBySourceId(String sourceId) {
  for (final p in kKnownPacks) {
    if (p.sourceId == sourceId) return p;
  }
  return null;
}
