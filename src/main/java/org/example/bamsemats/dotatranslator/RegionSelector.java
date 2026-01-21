package org.example.bamsemats.dotatranslator;

import javafx.scene.Scene;
import javafx.scene.layout.Pane;
import javafx.scene.paint.Color;
import javafx.scene.shape.Rectangle;
import javafx.stage.Screen;
import javafx.stage.Stage;
import javafx.stage.StageStyle;

import java.awt.*;

public class RegionSelector {

    private Rectangle selectionRect;
    private double startX;
    private double startY;

    public Rectangle selectRegion(Stage owner) {
        Stage stage = new Stage(StageStyle.TRANSPARENT);
        stage.initOwner(owner);
        stage.setAlwaysOnTop(true);

        Pane root = new Pane();
        root.setStyle("-fx-background-color: rgba(0, 0, 0, 0.25);");

        Scene scene = new Scene(
                root,
                Screen.getPrimary().getBounds().getWidth(),
                Screen.getPrimary().getBounds().getHeight(),
                Color.TRANSPARENT
        );

        selectionRect = new Rectangle();
        selectionRect.setStroke(Color.RED);
        selectionRect.setStrokeWidth(2);
        selectionRect.setFill(Color.color(1, 0, 0, 0.15));

        root.getChildren().add(selectionRect);

        scene.setOnMousePressed(e -> {
            startX = e.getScreenX();
            startY = e.getScreenY();

            selectionRect.setX(startX);
            selectionRect.setY(startY);
            selectionRect.setWidth(0);
            selectionRect.setHeight(0);
        });

        scene.setOnMouseDragged(e -> {
            double currentX = e.getScreenX();
            double currentY = e.getScreenY();

            selectionRect.setX(Math.min(startX, currentX));
            selectionRect.setY(Math.min(startY, currentY));
            selectionRect.setWidth(Math.abs(currentX - startX));
            selectionRect.setHeight(Math.abs(currentY - startY));
        });

        scene.setOnMouseReleased(e -> stage.close());

        stage.setScene(scene);
        stage.showAndWait();

        return selectionRect;
    }

    public static java.awt.Rectangle toAwt(Rectangle fxRect) {
        return new java.awt.Rectangle(
                (int) fxRect.getX(),
                (int) fxRect.getY(),
                (int) fxRect.getWidth(),
                (int) fxRect.getHeight()
        );
    }
}
