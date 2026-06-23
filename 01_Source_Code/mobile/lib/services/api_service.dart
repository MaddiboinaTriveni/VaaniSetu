// lib/services/api_service.dart
// Handles all HTTP calls to the VaaniSetu FastAPI backend.

import 'dart:io';
import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  // Change this to your deployed URL for production
  // For local dev: use your machine's IP (not localhost) since
  // the emulator can't reach localhost. E.g. http://192.168.1.10:8000
  static const String baseUrl = 'http://10.0.2.2:8000'; // Android emulator → host

  // ── Health check ─────────────────────────────────────────────────────────
  static Future<Map<String, dynamic>> healthCheck() async {
    final response = await http
        .get(Uri.parse('$baseUrl/health'))
        .timeout(const Duration(seconds: 10));
    return jsonDecode(response.body);
  }

  // ── Full pipeline ─────────────────────────────────────────────────────────
  static Future<PipelineResult> runPipeline({
    required File imageFile,
    required String language,
    String? whatsappNumber,
  }) async {
    final uri = Uri.parse('$baseUrl/pipeline');
    final request = http.MultipartRequest('POST', uri);

    request.files.add(await http.MultipartFile.fromPath('file', imageFile.path));
    request.fields['language'] = language;

    if (whatsappNumber != null && whatsappNumber.isNotEmpty) {
      request.fields['send_whatsapp'] = 'true';
      request.fields['whatsapp_number'] = whatsappNumber;
    }

    final streamedResponse = await request.send().timeout(
      const Duration(seconds: 60),
    );
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode != 200) {
      throw ApiException(
        'Pipeline failed (${response.statusCode})',
        jsonDecode(response.body),
      );
    }

    final data = jsonDecode(response.body);
    return PipelineResult.fromJson(data, baseUrl);
  }

  // ── Audio URL builder ─────────────────────────────────────────────────────
  static String audioUrl(String audioId) => '$baseUrl/audio/$audioId';
}

// ── Data models ───────────────────────────────────────────────────────────────

class ApiException implements Exception {
  final String message;
  final dynamic details;
  ApiException(this.message, [this.details]);
  @override
  String toString() => message;
}

class PipelineResult {
  final bool success;
  final String language;
  final OcrResult ocr;
  final DocumentSummary summary;
  final AudioResult audio;

  PipelineResult({
    required this.success,
    required this.language,
    required this.ocr,
    required this.summary,
    required this.audio,
  });

  factory PipelineResult.fromJson(Map<String, dynamic> json, String baseUrl) {
    return PipelineResult(
      success: json['success'] ?? false,
      language: json['language'] ?? 'telugu',
      ocr: OcrResult.fromJson(json['ocr'] ?? {}),
      summary: DocumentSummary.fromJson(json['summary'] ?? {}),
      audio: AudioResult.fromJson(json['audio'] ?? {}, baseUrl),
    );
  }
}

class OcrResult {
  final double confidence;
  final int wordCount;
  final String docType;
  final bool lowQuality;
  final String textPreview;

  OcrResult({
    required this.confidence,
    required this.wordCount,
    required this.docType,
    required this.lowQuality,
    required this.textPreview,
  });

  factory OcrResult.fromJson(Map<String, dynamic> json) => OcrResult(
        confidence: (json['confidence'] ?? 0.0).toDouble(),
        wordCount: json['word_count'] ?? 0,
        docType: json['doc_type'] ?? 'legal_document',
        lowQuality: json['low_quality'] ?? false,
        textPreview: json['text_preview'] ?? '',
      );
}

class DocumentSummary {
  final String documentType;
  final String parties;
  final String actionRequired;
  final String consequence;
  final String urgency;
  final String? keyDate;
  final bool mockMode;

  DocumentSummary({
    required this.documentType,
    required this.parties,
    required this.actionRequired,
    required this.consequence,
    required this.urgency,
    this.keyDate,
    required this.mockMode,
  });

  factory DocumentSummary.fromJson(Map<String, dynamic> json) => DocumentSummary(
        documentType: json['document_type'] ?? 'Legal Document',
        parties: json['parties'] ?? '—',
        actionRequired: json['action_required'] ?? '—',
        consequence: json['consequence'] ?? '—',
        urgency: json['urgency'] ?? 'medium',
        keyDate: json['key_date'],
        mockMode: json['mock_mode'] ?? false,
      );
}

class AudioResult {
  final bool success;
  final String? audioId;
  final String? audioUrl;
  final int? durationEstimate;
  final String? engine;

  AudioResult({
    required this.success,
    this.audioId,
    this.audioUrl,
    this.durationEstimate,
    this.engine,
  });

  factory AudioResult.fromJson(Map<String, dynamic> json, String baseUrl) {
    final audioId = json['audio_id'];
    return AudioResult(
      success: json['success'] ?? false,
      audioId: audioId,
      audioUrl: audioId != null ? '$baseUrl/audio/$audioId' : null,
      durationEstimate: json['duration_estimate'],
      engine: json['engine'],
    );
  }
}
