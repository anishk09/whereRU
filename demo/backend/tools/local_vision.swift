import Foundation
import Vision

// macOS Vision runs on this Mac; no network service or API key is used.
guard CommandLine.arguments.count == 2 else { exit(2) }
do {
    let handler = VNImageRequestHandler(url: URL(fileURLWithPath: CommandLine.arguments[1]))
    let classify = VNClassifyImageRequest()
    let crop = VNClassifyImageRequest()
    crop.regionOfInterest = CGRect(x: 0.28, y: 0.15, width: 0.44, height: 0.68)
    let text = VNRecognizeTextRequest()
    text.recognitionLevel = .accurate
    text.usesLanguageCorrection = false
    try handler.perform([classify, crop, text])
    let labels = Array(((classify.results ?? [])+(crop.results ?? [])).sorted { $0.confidence > $1.confidence }.prefix(30)).map { ["label": $0.identifier, "score": Double($0.confidence)] as [String: Any] }
    let words = (text.results ?? []).compactMap { $0.topCandidates(1).first }.filter { $0.confidence >= 0.3 }.map { $0.string }
    let result: [String: Any] = ["labels": labels, "text": words, "engine": "Apple Vision (on-device)"]
    FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: result))
} catch {
    FileHandle.standardOutput.write(Data("{\"labels\":[],\"text\":[],\"engine\":\"unavailable\"}".utf8))
    exit(1)
}
