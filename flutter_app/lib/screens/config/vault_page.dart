import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:jarvis_ui/providers/config_provider.dart';
import 'package:jarvis_ui/widgets/form/form_widgets.dart';

class VaultPage extends StatelessWidget {
  const VaultPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<ConfigProvider>(
      builder: (context, cfg, _) {
        final vault = cfg.cfg['vault'] as Map<String, dynamic>? ?? {};

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            JarvisToggleField(
              label: 'Vault aktiv',
              value: vault['enabled'] == true,
              onChanged: (v) => cfg.set('vault.enabled', v),
              description: 'Knowledge Vault aktivieren/deaktivieren',
            ),
            const SizedBox(height: 8),
            JarvisToggleField(
              label: 'Dateiverschluesselung',
              value: vault['encrypt_files'] == true,
              onChanged: (v) => cfg.set('vault.encrypt_files', v),
              description: 'Vault .md Dateien verschluesseln (AES-256). '
                  'Standard: Aus (Obsidian-kompatibel). '
                  'An: Maximale Sicherheit, Obsidian kann Dateien nicht lesen.',
            ),
            const SizedBox(height: 8),
            JarvisToggleField(
              label: 'Auto-Save Recherchen',
              value: vault['auto_save_research'] == true,
              onChanged: (v) => cfg.set('vault.auto_save_research', v),
              description: 'Web-Recherchen automatisch im Vault speichern',
            ),
          ],
        );
      },
    );
  }
}
