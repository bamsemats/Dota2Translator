package org.example.bamsemats.dotatranslator;

import java.time.LocalDate;
import java.util.prefs.Preferences;

public class UsageTracker {

    private static final String PREF_OCR_REQUESTS = "ocrRequestsCount";
    private static final String PREF_TRANSLATION_CHARS = "translationCharactersCount";
    private static final String PREF_LAST_RESET_MONTH = "lastResetMonth";
    private static final String PREF_LAST_RESET_YEAR = "lastResetYear";

    private static final int OCR_FREE_TIER_LIMIT = 1000; // Requests per month for TEXT_DETECTION
    private static final int TRANSLATION_FREE_TIER_LIMIT = 500000; // Characters per month

    private static Preferences prefs = Preferences.userNodeForPackage(UsageTracker.class);

    private UsageTracker() {
        // Private constructor to prevent instantiation
    }

    private static void resetMonthlyUsageIfNeeded() {
        LocalDate today = LocalDate.now();
        int currentMonth = today.getMonthValue();
        int currentYear = today.getYear();

        int lastResetMonth = prefs.getInt(PREF_LAST_RESET_MONTH, 0);
        int lastResetYear = prefs.getInt(PREF_LAST_RESET_YEAR, 0);

        if (currentYear > lastResetYear || (currentYear == lastResetYear && currentMonth > lastResetMonth)) {
            prefs.putInt(PREF_OCR_REQUESTS, 0);
            prefs.putInt(PREF_TRANSLATION_CHARS, 0);
            prefs.putInt(PREF_LAST_RESET_MONTH, currentMonth);
            prefs.putInt(PREF_LAST_RESET_YEAR, currentYear);
            System.out.println("UsageTracker: Monthly usage reset for " + today.getMonth() + " " + today.getYear());
        }
    }

    public static void incrementOcrRequests() {
        resetMonthlyUsageIfNeeded();
        int count = prefs.getInt(PREF_OCR_REQUESTS, 0);
        prefs.putInt(PREF_OCR_REQUESTS, count + 1);
        System.out.println("UsageTracker: OCR requests: " + (count + 1) + " / " + OCR_FREE_TIER_LIMIT);
    }

    public static void incrementTranslationCharacters(int characters) {
        resetMonthlyUsageIfNeeded();
        int count = prefs.getInt(PREF_TRANSLATION_CHARS, 0);
        prefs.putInt(PREF_TRANSLATION_CHARS, count + characters);
        System.out.println("UsageTracker: Translation characters: " + (count + characters) + " / " + TRANSLATION_FREE_TIER_LIMIT);
    }

    public static int getOcrRequests() {
        resetMonthlyUsageIfNeeded();
        return prefs.getInt(PREF_OCR_REQUESTS, 0);
    }

    public static int getTranslationCharacters() {
        resetMonthlyUsageIfNeeded();
        return prefs.getInt(PREF_TRANSLATION_CHARS, 0);
    }

    public static int getOcrFreeTierLimit() {
        return OCR_FREE_TIER_LIMIT;
    }

    public static int getTranslationFreeTierLimit() {
        return TRANSLATION_FREE_TIER_LIMIT;
    }

    public static boolean isOcrLimitReached() {
        return getOcrRequests() >= OCR_FREE_TIER_LIMIT;
    }

    public static boolean isTranslationLimitReached() {
        return getTranslationCharacters() >= TRANSLATION_FREE_TIER_LIMIT;
    }

    public static double getOcrUsagePercentage() {
        return (double) getOcrRequests() / OCR_FREE_TIER_LIMIT * 100;
    }

    public static double getTranslationUsagePercentage() {
        return (double) getTranslationCharacters() / TRANSLATION_FREE_TIER_LIMIT * 100;
    }
}
