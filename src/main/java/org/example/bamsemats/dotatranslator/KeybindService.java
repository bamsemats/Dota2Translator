package org.example.bamsemats.dotatranslator;

import com.github.kwhat.jnativehook.GlobalScreen;
import com.github.kwhat.jnativehook.NativeHookException;
import com.github.kwhat.jnativehook.keyboard.NativeKeyEvent;
import com.github.kwhat.jnativehook.keyboard.NativeKeyListener;

import java.util.logging.Level;
import java.util.logging.Logger;

public class KeybindService implements NativeKeyListener {

    private Runnable onKeyPressed;
    private int snapshotKey;

    public KeybindService(Runnable onKeyPressed, int initialKey) {
        this.onKeyPressed = onKeyPressed;
        this.snapshotKey = initialKey;
    }

    public void register() {
        try {
            Logger logger = Logger.getLogger(GlobalScreen.class.getPackage().getName());
            logger.setLevel(Level.OFF);
            logger.setUseParentHandlers(false);

            GlobalScreen.registerNativeHook();
        } catch (NativeHookException ex) {
            System.err.println("There was a problem registering the native hook.");
            System.err.println(ex.getMessage());
            return;
        }
        GlobalScreen.addNativeKeyListener(this);
        System.out.println("Key listener registered. Press " + NativeKeyEvent.getKeyText(snapshotKey) + " to take a snapshot.");
    }

    public void unregister() {
        try {
            GlobalScreen.removeNativeKeyListener(this);
            GlobalScreen.unregisterNativeHook();
        } catch (NativeHookException ex) {
            System.err.println("There was a problem unregistering the native hook.");
            System.err.println(ex.getMessage());
        }
    }

    public void setSnapshotKey(int snapshotKey) {
        this.snapshotKey = snapshotKey;
        System.out.println("Snapshot key updated to: " + NativeKeyEvent.getKeyText(snapshotKey));
    }

    @Override
    public void nativeKeyPressed(NativeKeyEvent e) {
        if (e.getKeyCode() == snapshotKey) {
            System.out.println("Snapshot key pressed!");
            if (onKeyPressed != null) {
                onKeyPressed.run();
            }
        }
    }

    @Override
    public void nativeKeyReleased(NativeKeyEvent e) {
        // Not needed
    }

    @Override
    public void nativeKeyTyped(NativeKeyEvent e) {
        // Not needed
    }
}
