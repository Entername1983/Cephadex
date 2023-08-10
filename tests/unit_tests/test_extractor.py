import unittest
from unittest.mock import Mock, patch
from pathlib import Path
from models.extractors.extractor import extract_from_pdf, extract_from_pptx, extract_from_docx, get_duration
from models.extractors.extractor import extract_from_url, extract_from_wiki, extract_from_youtube, get_video_id, get_audio_content
from models.extractors.extractor_config import PAGES_PER_MIN, TOKENS_PER_PAGE
class TestExtractorMethods(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_files_dir = Path("tests\\test_files")

    def test_extract_from_pdf(self):
        test_file = self.test_files_dir / "pdf_sample_150kB.pdf"
        result = extract_from_pdf(test_file)
        self.assertIsInstance(result, str) # Test if the returned result is a string
        self.assertTrue(result) # Test if the returned result is not empty

    def test_extract_from_pptx(self):
        test_file = self.test_files_dir / "Free_Test_Data_100KB_PPTX.pptx"
        result = extract_from_pptx(test_file)
        self.assertIsInstance(result, str) # Test if the returned result is a string
        self.assertTrue(result) # Test if the returned result is not empty

    def test_extract_from_docx(self):
        test_file = self.test_files_dir / "docx_sample_100kb.docx"
        result = extract_from_docx(test_file)
        self.assertIsInstance(result, str) # Test if the returned result is a string
        self.assertTrue(result) # Test if the returned result is not empty

    def test_get_audio_content_wav(self):
        name = "wav_sample_eng.wav"
        # Assuming you have a sample audio file for testing
        audio_file = self.test_files_dir / name
        expected_duration = 23.68106575963719  # Assuming the duration is 60 seconds
        # Open the audio file in binary mode
        with open(audio_file, "rb") as file:
            result_duration = get_audio_content(file, name)
        assert result_duration == expected_duration

    def test_get_audio_content_mp3(self):
        # Assuming you have a sample audio file for testing
        name = "mp3_sample_eng.mp3"
        audio_file = self.test_files_dir / name
        expected_duration = 209.2638125  # Assuming the duration is 60 seconds
        # Open the audio file in binary mode
        with open(audio_file, "rb") as file:
            result_duration = get_audio_content(file, name)
        assert result_duration == expected_duration

    def test_get_duration_mp3(self):
        name = "mp3_sample_eng.mp3"
        audio_file_path = self.test_files_dir / name
        expected_duration = 209.2638125  # Assuming the duration is 60 seconds
        with open(audio_file_path, "rb") as file:
            result_duration = get_duration(file, name)
        assert result_duration == expected_duration


def test_extract_from_url_youtube():
    link_data = "https://www.youtube.com/watch?v=rcszE4xf_QI"
    expected_link_type = "youtube"
    result_text, result_link_type = extract_from_url(link_data)
    assert isinstance(result_text, str)
    assert result_link_type == expected_link_type

def test_extract_from_wiki():
    wiki_url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
    result_text = extract_from_wiki(wiki_url)
    assert isinstance(result_text, str)


def test_extract_from_youtube():
    youtube_url = "rcszE4xf_QI"
    result_text = extract_from_youtube(youtube_url)
    assert isinstance(result_text, str)


def test_get_video_id():
    link = "https://www.youtube.com/watch?v=rcszE4xf_QI"
    expected_video_id = "rcszE4xf_QI"
    result_video_id = get_video_id(link)
    assert result_video_id == expected_video_id

if __name__ == '__main__':
    unittest.main()






