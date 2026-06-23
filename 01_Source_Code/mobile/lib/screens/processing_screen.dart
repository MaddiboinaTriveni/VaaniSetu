// lib/screens/processing_screen.dart
// Screen 2: Animated progress while backend processes the document

import 'dart:io';
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'result_screen.dart';

class ProcessingScreen extends StatefulWidget {
  final File imageFile;
  final String language;

  const ProcessingScreen({
    super.key,
    required this.imageFile,
    required this.language,
  });

  @override
  State<ProcessingScreen> createState() => _ProcessingScreenState();
}

class _ProcessingScreenState extends State<ProcessingScreen>
    with TickerProviderStateMixin {
  int _currentStep = 0;
  bool _hasError = false;
  String _errorMessage = '';

  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  static const List<Map<String, String>> _steps = [
    {'icon': '📷', 'label': 'Reading document with OCR...', 'sub': 'Extracting text from image'},
    {'icon': '🧠', 'label': 'Understanding legal content...', 'sub': 'Identifying key information'},
    {'icon': '🌐', 'label': 'Translating to your language...', 'sub': 'Using IndicTrans2 AI model'},
    {'icon': '🔊', 'label': 'Generating voice summary...', 'sub': 'Creating audio explanation'},
  ];

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(vsync: this, duration: const Duration(seconds: 1))
      ..repeat(reverse: true);
    _pulseAnimation = Tween<double>(begin: 0.85, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
    _runPipeline();
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _runPipeline() async {
    // Advance steps with timing for UX feedback
    for (int i = 0; i < _steps.length; i++) {
      if (!mounted) return;
      setState(() => _currentStep = i);
      await Future.delayed(const Duration(milliseconds: 800));
    }

    try {
      final result = await ApiService.runPipeline(
        imageFile: widget.imageFile,
        language: widget.language,
      );

      if (!mounted) return;
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => ResultScreen(result: result),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _hasError = true;
        _errorMessage = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Analyzing...'),
        automaticallyImplyLeading: false,
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: _hasError ? _buildError() : _buildProgress(),
        ),
      ),
    );
  }

  Widget _buildProgress() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        // Document thumbnail
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: Image.file(
            widget.imageFile,
            height: 160,
            width: double.infinity,
            fit: BoxFit.cover,
          ),
        ),
        const SizedBox(height: 40),

        // Pulse animation circle
        ScaleTransition(
          scale: _pulseAnimation,
          child: Container(
            width: 100,
            height: 100,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: const Color(0xFF0F766E).withOpacity(0.1),
            ),
            child: Center(
              child: Text(
                _steps[_currentStep]['icon']!,
                style: const TextStyle(fontSize: 40),
              ),
            ),
          ),
        ),
        const SizedBox(height: 24),

        Text(
          _steps[_currentStep]['label']!,
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF1E293B)),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 8),
        Text(
          _steps[_currentStep]['sub']!,
          style: const TextStyle(fontSize: 14, color: Color(0xFF64748B)),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 32),

        // Step indicators
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: List.generate(_steps.length, (i) => AnimatedContainer(
            duration: const Duration(milliseconds: 300),
            margin: const EdgeInsets.symmetric(horizontal: 4),
            width: i == _currentStep ? 24 : 8,
            height: 8,
            decoration: BoxDecoration(
              color: i <= _currentStep
                  ? const Color(0xFF0F766E)
                  : const Color(0xFFCBD5E1),
              borderRadius: BorderRadius.circular(4),
            ),
          )),
        ),
        const SizedBox(height: 32),

        // Step checklist
        ..._steps.asMap().entries.map((e) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(
            children: [
              Icon(
                e.key < _currentStep
                    ? Icons.check_circle
                    : e.key == _currentStep
                        ? Icons.radio_button_checked
                        : Icons.radio_button_unchecked,
                color: e.key <= _currentStep
                    ? const Color(0xFF0F766E)
                    : const Color(0xFFCBD5E1),
                size: 20,
              ),
              const SizedBox(width: 10),
              Text(
                e.value['label']!,
                style: TextStyle(
                  fontSize: 13,
                  color: e.key <= _currentStep
                      ? const Color(0xFF1E293B)
                      : const Color(0xFF94A3B8),
                  fontWeight: e.key == _currentStep
                      ? FontWeight.w600
                      : FontWeight.normal,
                ),
              ),
            ],
          ),
        )),
      ],
    );
  }

  Widget _buildError() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.error_outline, size: 80, color: Color(0xFFDC2626)),
        const SizedBox(height: 20),
        const Text('Analysis failed', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Color(0xFF1E293B))),
        const SizedBox(height: 12),
        Text(_errorMessage, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFF64748B), height: 1.5)),
        const SizedBox(height: 32),
        ElevatedButton.icon(
          icon: const Icon(Icons.arrow_back),
          label: const Text('Try Again'),
          onPressed: () => Navigator.pop(context),
        ),
        const SizedBox(height: 12),
        OutlinedButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Go Back'),
        ),
      ],
    );
  }
}
