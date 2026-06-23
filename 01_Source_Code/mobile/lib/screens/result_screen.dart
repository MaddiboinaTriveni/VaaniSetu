// lib/screens/result_screen.dart
// Screen 3: Summary cards + audio playback + share options

import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:just_audio/just_audio.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/api_service.dart';
import 'home_screen.dart';

class ResultScreen extends StatefulWidget {
  final PipelineResult result;
  const ResultScreen({super.key, required this.result});

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  late AudioPlayer _player;
  bool _isPlaying = false;
  bool _isLoadingAudio = true;
  bool _audioError = false;
  Duration _position = Duration.zero;
  Duration _duration = Duration.zero;

  @override
  void initState() {
    super.initState();
    _player = AudioPlayer();
    _initAudio();
  }

  Future<void> _initAudio() async {
    final audioUrl = widget.result.audio.audioUrl;
    if (audioUrl == null) {
      setState(() { _audioError = true; _isLoadingAudio = false; });
      return;
    }
    try {
      await _player.setUrl(audioUrl);
      _player.positionStream.listen((p) {
        if (mounted) setState(() => _position = p);
      });
      _player.durationStream.listen((d) {
        if (mounted && d != null) setState(() => _duration = d);
      });
      _player.playerStateStream.listen((state) {
        if (mounted) setState(() => _isPlaying = state.playing);
      });
      setState(() => _isLoadingAudio = false);
      // Auto-play
      await _player.play();
    } catch (e) {
      if (mounted) setState(() { _audioError = true; _isLoadingAudio = false; });
    }
  }

  @override
  void dispose() {
    _player.dispose();
    super.dispose();
  }

  Future<void> _togglePlay() async {
    if (_isPlaying) {
      await _player.pause();
    } else {
      await _player.play();
    }
  }

  void _shareResult() {
    final s = widget.result.summary;
    final text = '''📜 VaaniSetu Legal Document Summary

Document: ${s.documentType}
Parties: ${s.parties}

⚠️ What you must do:
${s.actionRequired}

❗ If ignored:
${s.consequence}

${s.keyDate != null ? '📅 Important date: ${s.keyDate}' : ''}

📞 NALSA Legal Aid: 15100 (free)
''';
    Share.share(text, subject: 'Legal Notice Summary — VaaniSetu');
  }

  Future<void> _callNalsa() async {
    final uri = Uri(scheme: 'tel', path: '15100');
    if (await canLaunchUrl(uri)) await launchUrl(uri);
  }

  String _formatDuration(Duration d) {
    final m = d.inMinutes.remainder(60).toString().padLeft(2, '0');
    final s = d.inSeconds.remainder(60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  Color get _urgencyColor {
    switch (widget.result.summary.urgency) {
      case 'high':   return const Color(0xFFDC2626);
      case 'medium': return const Color(0xFFD97706);
      default:       return const Color(0xFF16A34A);
    }
  }

  String get _urgencyLabel {
    switch (widget.result.summary.urgency) {
      case 'high':   return '🔴 URGENT';
      case 'medium': return '🟡 IMPORTANT';
      default:       return '🟢 ROUTINE';
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.result.summary;

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        title: const Text('Document Summary'),
        actions: [
          IconButton(
            icon: const Icon(Icons.share_outlined),
            onPressed: _shareResult,
            tooltip: 'Share summary',
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Urgency banner
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 16),
              decoration: BoxDecoration(
                color: _urgencyColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: _urgencyColor.withOpacity(0.3)),
              ),
              child: Row(
                children: [
                  Text(_urgencyLabel,
                      style: TextStyle(fontWeight: FontWeight.bold, color: _urgencyColor, fontSize: 15)),
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: _urgencyColor.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      s.documentType,
                      style: TextStyle(fontSize: 12, color: _urgencyColor, fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Audio player card
            _buildAudioCard(),
            const SizedBox(height: 16),

            // Key date highlight
            if (s.keyDate != null) ...[
              _buildDateCard(s.keyDate!),
              const SizedBox(height: 16),
            ],

            // 4 summary info cards
            _buildInfoCard(
              icon: '👥',
              label: 'Who is involved',
              value: s.parties,
              color: const Color(0xFF0F766E),
            ),
            const SizedBox(height: 12),
            _buildInfoCard(
              icon: '⚠️',
              label: 'What you MUST do',
              value: s.actionRequired,
              color: _urgencyColor,
              highlight: true,
            ),
            const SizedBox(height: 12),
            _buildInfoCard(
              icon: '❗',
              label: 'If you ignore this',
              value: s.consequence,
              color: const Color(0xFF7C3AED),
            ),
            const SizedBox(height: 20),

            // OCR confidence row
            _buildOcrBadge(),
            const SizedBox(height: 20),

            // Mock mode notice
            if (s.mockMode)
              Container(
                padding: const EdgeInsets.all(12),
                margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(
                  color: const Color(0xFFFEF9C3),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFFFDE047)),
                ),
                child: const Row(
                  children: [
                    Text('⚡', style: TextStyle(fontSize: 20)),
                    SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Demo mode — add GROQ_API_KEY in .env for full AI summarization',
                        style: TextStyle(fontSize: 12, color: Color(0xFF713F12)),
                      ),
                    ),
                  ],
                ),
              ),

            // Action buttons
            ElevatedButton.icon(
              icon: const Icon(Icons.share),
              label: const Text('Share this summary'),
              onPressed: _shareResult,
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF1D4ED8)),
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              icon: const Icon(Icons.phone),
              label: const Text('Call NALSA Free Legal Aid — 15100'),
              onPressed: _callNalsa,
              style: OutlinedButton.styleFrom(
                minimumSize: const Size(double.infinity, 50),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
            const SizedBox(height: 10),
            TextButton.icon(
              icon: const Icon(Icons.arrow_back),
              label: const Text('Translate another document'),
              onPressed: () => Navigator.pushAndRemoveUntil(
                context,
                MaterialPageRoute(builder: (_) => const HomeScreen()),
                (r) => false,
              ),
              style: TextButton.styleFrom(
                minimumSize: const Size(double.infinity, 48),
              ),
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildAudioCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0F766E),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.volume_up, color: Colors.white, size: 20),
              SizedBox(width: 8),
              Text('Voice Summary', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Hear this notice explained in your language',
            style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 12),
          ),
          const SizedBox(height: 16),

          if (_isLoadingAudio)
            const Center(child: CircularProgressIndicator(color: Colors.white))
          else if (_audioError)
            const Text('Audio unavailable — check internet connection',
                style: TextStyle(color: Colors.white70, fontSize: 13))
          else ...[
            // Progress slider
            SliderTheme(
              data: SliderTheme.of(context).copyWith(
                activeTrackColor: Colors.white,
                inactiveTrackColor: Colors.white30,
                thumbColor: Colors.white,
                overlayColor: Colors.white24,
                trackHeight: 3,
                thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 7),
              ),
              child: Slider(
                value: _duration.inMilliseconds > 0
                    ? _position.inMilliseconds / _duration.inMilliseconds
                    : 0.0,
                onChanged: (v) {
                  _player.seek(Duration(
                    milliseconds: (v * _duration.inMilliseconds).round(),
                  ));
                },
              ),
            ),
            Row(
              children: [
                Text(_formatDuration(_position),
                    style: const TextStyle(color: Colors.white70, fontSize: 12)),
                const Spacer(),
                GestureDetector(
                  onTap: _togglePlay,
                  child: Container(
                    width: 52,
                    height: 52,
                    decoration: const BoxDecoration(
                      color: Colors.white,
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      _isPlaying ? Icons.pause : Icons.play_arrow,
                      color: const Color(0xFF0F766E),
                      size: 30,
                    ),
                  ),
                ),
                const Spacer(),
                Text(_formatDuration(_duration),
                    style: const TextStyle(color: Colors.white70, fontSize: 12)),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildDateCard(String date) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFEF3C7),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFFDE68A)),
      ),
      child: Row(
        children: [
          const Text('📅', style: TextStyle(fontSize: 28)),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('IMPORTANT DATE',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold,
                        color: Color(0xFF92400E), letterSpacing: 0.8)),
                const SizedBox(height: 4),
                Text(date,
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold,
                        color: Color(0xFF78350F))),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.copy, size: 18, color: Color(0xFF92400E)),
            onPressed: () {
              Clipboard.setData(ClipboardData(text: date));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Date copied'), duration: Duration(seconds: 1)),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildInfoCard({
    required String icon,
    required String label,
    required String value,
    required Color color,
    bool highlight = false,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: highlight ? color.withOpacity(0.06) : Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: highlight ? color.withOpacity(0.3) : const Color(0xFFE2E8F0),
          width: highlight ? 1.5 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(icon, style: const TextStyle(fontSize: 18)),
              const SizedBox(width: 8),
              Text(label.toUpperCase(),
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: color,
                    letterSpacing: 0.6,
                  )),
            ],
          ),
          const SizedBox(height: 8),
          Text(value,
              style: const TextStyle(
                fontSize: 15,
                color: Color(0xFF1E293B),
                height: 1.5,
              )),
        ],
      ),
    );
  }

  Widget _buildOcrBadge() {
    final conf = widget.result.ocr.confidence;
    final confColor = conf > 75
        ? const Color(0xFF16A34A)
        : conf > 50
            ? const Color(0xFFD97706)
            : const Color(0xFFDC2626);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFF1F5F9),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          const Text('🔍', style: TextStyle(fontSize: 16)),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('OCR Confidence: ${conf.toStringAsFixed(0)}%',
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600,
                        color: Color(0xFF475569))),
                const SizedBox(height: 4),
                LinearProgressIndicator(
                  value: conf / 100,
                  backgroundColor: const Color(0xFFE2E8F0),
                  valueColor: AlwaysStoppedAnimation<Color>(confColor),
                  borderRadius: BorderRadius.circular(4),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Text('${widget.result.ocr.wordCount} words',
              style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8))),
        ],
      ),
    );
  }
}
