// lib/screens/home_screen.dart
// Screen 1: Language selection + document capture

import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'processing_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  String _selectedLanguage = 'telugu';
  File? _selectedImage;
  final ImagePicker _picker = ImagePicker();

  static const Map<String, Map<String, String>> _languages = {
    'telugu':    {'label': 'తెలుగు', 'english': 'Telugu'},
    'hindi':     {'label': 'हिन्दी', 'english': 'Hindi'},
    'tamil':     {'label': 'தமிழ்', 'english': 'Tamil'},
    'kannada':   {'label': 'ಕನ್ನಡ', 'english': 'Kannada'},
    'malayalam': {'label': 'മലയാളം', 'english': 'Malayalam'},
    'marathi':   {'label': 'मराठी', 'english': 'Marathi'},
    'bengali':   {'label': 'বাংলা', 'english': 'Bengali'},
    'gujarati':  {'label': 'ગુજરાતી', 'english': 'Gujarati'},
  };

  Future<void> _pickImage(ImageSource source) async {
    final XFile? picked = await _picker.pickImage(
      source: source,
      imageQuality: 90,
      maxWidth: 2000,
    );
    if (picked != null) {
      setState(() => _selectedImage = File(picked.path));
    }
  }

  void _analyze() {
    if (_selectedImage == null) return;
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ProcessingScreen(
          imageFile: _selectedImage!,
          language: _selectedLanguage,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Column(
          children: [
            Text('वाणीसेतु', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            Text('VaaniSetu', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w400)),
          ],
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Hero banner
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFF0F766E).withOpacity(0.08),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFF0F766E).withOpacity(0.2)),
              ),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('📜 Know your legal rights', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF0F766E))),
                  SizedBox(height: 8),
                  Text(
                    'Photograph any court notice or legal document.\nWe will explain it in your language.',
                    style: TextStyle(fontSize: 14, color: Color(0xFF475569), height: 1.5),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Language selector
            const Text('Select your language', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF374151))),
            const SizedBox(height: 10),
            Container(
              decoration: BoxDecoration(
                border: Border.all(color: const Color(0xFFD1D5DB)),
                borderRadius: BorderRadius.circular(12),
              ),
              child: DropdownButtonFormField<String>(
                value: _selectedLanguage,
                decoration: const InputDecoration(
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                ),
                items: _languages.entries.map((e) => DropdownMenuItem(
                  value: e.key,
                  child: Text('${e.value['label']}  —  ${e.value['english']}',
                      style: const TextStyle(fontSize: 15)),
                )).toList(),
                onChanged: (v) => setState(() => _selectedLanguage = v!),
              ),
            ),
            const SizedBox(height: 24),

            // Image preview / placeholder
            const Text('Document photo', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF374151))),
            const SizedBox(height: 10),
            GestureDetector(
              onTap: () => _showSourceDialog(),
              child: Container(
                width: double.infinity,
                height: 220,
                decoration: BoxDecoration(
                  color: const Color(0xFFF8FAFC),
                  border: Border.all(
                    color: _selectedImage != null
                        ? const Color(0xFF0F766E)
                        : const Color(0xFFCBD5E1),
                    width: 2,
                    strokeAlign: BorderSide.strokeAlignInside,
                  ),
                  borderRadius: BorderRadius.circular(16),
                ),
                clipBehavior: Clip.hardEdge,
                child: _selectedImage != null
                    ? Stack(
                        fit: StackFit.expand,
                        children: [
                          Image.file(_selectedImage!, fit: BoxFit.cover),
                          Positioned(
                            top: 8, right: 8,
                            child: GestureDetector(
                              onTap: () => setState(() => _selectedImage = null),
                              child: Container(
                                padding: const EdgeInsets.all(6),
                                decoration: BoxDecoration(
                                  color: Colors.black54,
                                  borderRadius: BorderRadius.circular(20),
                                ),
                                child: const Icon(Icons.close, color: Colors.white, size: 18),
                              ),
                            ),
                          ),
                        ],
                      )
                    : const Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.add_a_photo_outlined, size: 48, color: Color(0xFF94A3B8)),
                          SizedBox(height: 12),
                          Text('Tap to photograph document', style: TextStyle(fontSize: 15, color: Color(0xFF64748B), fontWeight: FontWeight.w500)),
                          SizedBox(height: 4),
                          Text('or upload from gallery', style: TextStyle(fontSize: 13, color: Color(0xFF94A3B8))),
                        ],
                      ),
              ),
            ),
            const SizedBox(height: 12),

            // Quick pick buttons
            Row(
              children: [
                Expanded(child: OutlinedButton.icon(
                  icon: const Icon(Icons.camera_alt_outlined),
                  label: const Text('Camera'),
                  onPressed: () => _pickImage(ImageSource.camera),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                )),
                const SizedBox(width: 12),
                Expanded(child: OutlinedButton.icon(
                  icon: const Icon(Icons.photo_library_outlined),
                  label: const Text('Gallery'),
                  onPressed: () => _pickImage(ImageSource.gallery),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                )),
              ],
            ),
            const SizedBox(height: 24),

            // Analyze button
            ElevatedButton.icon(
              icon: const Icon(Icons.translate),
              label: const Text('Translate & Explain'),
              onPressed: _selectedImage != null ? _analyze : null,
            ),
            const SizedBox(height: 20),

            // NALSA helpline banner
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: const Color(0xFFEFF6FF),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFBFDBFE)),
              ),
              child: const Row(
                children: [
                  Text('📞', style: TextStyle(fontSize: 24)),
                  SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Free legal help', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF1D4ED8))),
                        Text('NALSA Legal Aid Helpline: 15100', style: TextStyle(fontSize: 13, color: Color(0xFF3B82F6))),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showSourceDialog() {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (_) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            Container(width: 40, height: 4, decoration: BoxDecoration(color: Colors.grey[300], borderRadius: BorderRadius.circular(2))),
            const SizedBox(height: 16),
            ListTile(
              leading: const Icon(Icons.camera_alt, color: Color(0xFF0F766E)),
              title: const Text('Take a photo'),
              onTap: () { Navigator.pop(context); _pickImage(ImageSource.camera); },
            ),
            ListTile(
              leading: const Icon(Icons.photo_library, color: Color(0xFF0F766E)),
              title: const Text('Choose from gallery'),
              onTap: () { Navigator.pop(context); _pickImage(ImageSource.gallery); },
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}
