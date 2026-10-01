import QtQuick
import QtMultimedia

// Live picture from the camera whose name matches `cameraName`. Loaded only on demand:
// it holds the camera open, and needs Qt Multimedia.
Rectangle {
    id: root
    property string cameraName: ""
    color: "black"
    radius: theme.radius
    clip: true

    MediaDevices { id: devices }
    CaptureSession {
        camera: Camera {
            cameraDevice: devices.videoInputs.find(d => d.description === root.cameraName)
                          || devices.defaultVideoInput
            active: true
        }
        videoOutput: output
    }
    VideoOutput { id: output; anchors.fill: parent; fillMode: VideoOutput.PreserveAspectFit }
}
