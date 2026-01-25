package org.example.bamsemats.dotatranslator;

import java.util.List; // Import List

public class OcrResult {
    private List<Line> lines; // Changed to list of Line objects

    public OcrResult() {
        // Default constructor for Jackson
    }

    public OcrResult(List<Line> lines) {
        this.lines = lines;
    }

    public List<Line> getLines() {
        return lines;
    }

    public void setLines(List<Line> lines) {
        this.lines = lines;
    }

    @Override
    public String toString() {
        return "OcrResult{"
               + "lines=" + lines +
               '}';
    }

    // Inner static class to represent each line with its detected language
    public static class Line {
        private String text;
        private String language;

        public Line() {
            // Default constructor for Jackson
        }

        public Line(String text, String language) {
            this.text = text;
            this.language = language;
        }

        public String getText() {
            return text;
        }

        public void setText(String text) {
            this.text = text;
        }

        public String getLanguage() {
            return language;
        }

        public void setLanguage(String language) {
            this.language = language;
        }

        @Override
        public String toString() {
            return "Line{"
                   + "text='" + text + '\'' +
                   ", language='" + language + '\'' +
                   '}';
        }
    }
}
