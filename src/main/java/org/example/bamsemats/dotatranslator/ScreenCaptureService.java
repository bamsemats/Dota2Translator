package org.example.bamsemats.dotatranslator;

import org.example.bamsemats.dotatranslator.OcrService;

import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.IOException;
import java.util.Timer;
import java.util.TimerTask;

public class ScreenCaptureService {

    private final Robot robot;
    private final Rectangle chatRegion;
    private final OcrService ocrService;

    public ScreenCaptureService(Rectangle chatRegion) {
        try {
            this.robot = new Robot();
        } catch (AWTException e) {
            throw new RuntimeException(e);
        }

        this.chatRegion = chatRegion;
        this.ocrService = new OcrService(true);
    }

    private Timer timer;
    public void start() {
        timer = new Timer(true);

        timer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                try {
                    captureAndProcess();
                } catch (IOException e) {
                    throw new RuntimeException(e);
                }
            }
        }, 0, 1000);
    }

    public void stop() {
        if (timer != null) {
            timer.cancel();
            timer.purge();
        }
    }

    private void captureAndProcess() throws IOException {
        BufferedImage image = robot.createScreenCapture(chatRegion);
        String text = ocrService.extractText(image);

        if (!text.isBlank()) {
            System.out.println("OCR OUTPUT:");
            System.out.println(text);
            System.out.println("--------------");
        }

        ImageIO.write(image, "png",
                new File("debug_chat_capture.png"));

    }
}
