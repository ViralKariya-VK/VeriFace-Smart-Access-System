import numpy as np
import cv2
import os
import threading
from django.conf import settings
import onnxruntime


class FaceEngine:
    """
    Wraps InsightFace ArcFace model.
    Handles two jobs:
    1. Enrollment — extract embedding from a photo and save it
    2. Recognition — compare a live frame against stored embeddings
    
    Why a class instead of just functions?
    The InsightFace model is heavy to load (~500MB).
    We load it once when the class is instantiated and reuse it.
    If we used plain functions, we'd risk loading the model multiple times.
    """

    _instance = None

    def __new__(cls):
        # Singleton — model loads once, lives in memory
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.app = None
        self._lock = threading.Lock()  # detector settings are shared state
        self._load_model()

    def _load_model(self):
        """
        Load InsightFace ArcFace model.
        
        det_size=(320, 320) — face detector input size
        Smaller = faster but misses small/distant faces
        Larger = slower but more accurate for distant faces
        320x320 is a good balance for a door camera ~1-2 meters away
        Alternative: (640, 640) if your camera is further away
        """
        try:
            import insightface
            from insightface.app import FaceAnalysis

            # Auto-select best available provider
            # Priority: CoreML (M4 GPU) > CPU (Apple AMX)
            # Why not just always use CoreML?
            # CoreML provider isn't available on all platforms —
            # Windows, Linux users won't have it.
            # This way the code works on any machine automatically.
            available = onnxruntime.get_available_providers()

            # CoreML has shape rank mismatch with InsightFace's detector on M4
            # Specifically the face detection model outputs {1,1,1,800,1} vs
            # expected {3200,1} — known onnxruntime + CoreML compatibility issue
            # CPU provider uses Apple AMX on M4 which is fast enough for 2 FPS
            providers = ['CPUExecutionProvider']
            print("💻 Using CPU provider (AMX accelerated on M4)")

            self.app = FaceAnalysis(
                name='buffalo_l',
                providers=providers
            )

            self.app.prepare(ctx_id=0, det_size=(320, 320))
            print("FaceEngine loaded — ArcFace model ready")

        except Exception as e:
            print(f"FaceEngine failed to load: {e}")
            self.app = None

    def get_embedding(self, image):
        """
        Extract 512-d ArcFace embedding from an image.
        
        Args:
            image: numpy array (BGR, as returned by OpenCV)
        
        Returns:
            embedding as numpy array (512,) or None if no face found
        
        Why return only the first face?
        Enrollment photos should have exactly one face.
        If multiple faces detected, we take the largest (most prominent) one.
        """
        if self.app is None:
            return None

        # Phone photos are 12+ megapixels — shrink first, detection doesn't need them
        h, w = image.shape[:2]
        if max(h, w) > 1280:
            scale = 1280 / max(h, w)
            image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

        # InsightFace expects BGR — OpenCV default, no conversion needed
        with self._lock:
            faces = self.app.get(image)

            if not faces:
                # Enrollment is a one-off, so spend more time looking: a face that
                # is small in a big photo is missed by the fast 320px live detector.
                self.app.prepare(ctx_id=0, det_size=(640, 640))
                try:
                    faces = self.app.get(image)
                finally:
                    self.app.prepare(ctx_id=0, det_size=(320, 320))

        if not faces:
            return None

        if len(faces) > 1:
            # Multiple faces — pick the largest bounding box
            # Largest face = closest to camera = most likely the person enrolling
            faces = sorted(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]), reverse=True)

        return faces[0].embedding  # 512-d numpy array

    def enroll_face(self, image_path, username):
        """
        Generate and save face embedding from an enrollment photo.
        Called once during registration.

        Args:
            image_path: absolute path to uploaded face image
            username: used for naming the .npy file

        Returns:
            (filename, full_path) tuple or raises exception
        
        Why .npy format?
        np.save/np.load is the fastest way to persist numpy arrays.
        Alternative: JSONField storing list of 512 floats — works but
        slower to load and takes more storage (text vs binary)
        Alternative: BinaryField — works but you'd need to handle
        serialization manually. .npy handles that for us.
        """
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not read image at {image_path}")

        embedding = self.get_embedding(image)
        if embedding is None:
            raise ValueError("No face detected in the uploaded image. Please upload a clear front-facing photo.")

        # Save embedding
        embedding_dir = os.path.join(settings.MEDIA_ROOT, 'face_embeddings')
        os.makedirs(embedding_dir, exist_ok=True)

        filename = f"{username}_embedding.npy"
        full_path = os.path.join(embedding_dir, filename)
        np.save(full_path, embedding)

        print(f"Face enrolled for {username} — embedding saved")
        return filename, full_path

    def compare(self, embedding_a, embedding_b):
        """
        Compute cosine similarity between two embeddings.
        
        Returns float between -1 and 1.
        Above 0.4 = same person (for ArcFace buffalo_l model)
        
        Why 0.4 threshold?
        InsightFace's own documentation recommends 0.3-0.5 for buffalo_l.
        0.4 is middle ground — not too strict (rejects real users),
        not too loose (lets in imposters).
        You can tune this via .env if needed.
        """
        norm_a = embedding_a / np.linalg.norm(embedding_a)
        norm_b = embedding_b / np.linalg.norm(embedding_b)
        return float(np.dot(norm_a, norm_b))

    @staticmethod
    def _crop(frame, face, pad=30):
        """Face crop with a little context around it — nicer in the access log."""
        bbox = face.bbox.astype(int)
        h, w = frame.shape[:2]
        x1, y1 = max(0, bbox[0] - pad), max(0, bbox[1] - pad)
        x2, y2 = min(w, bbox[2] + pad), min(h, bbox[3] + pad)
        return frame[y1:y2, x1:x2]

    def recognize(self, frame, stored_embeddings, threshold=0.4,
                  min_face=60, min_det_score=0.6):
        """
        Check if any face in frame matches any stored embedding.

        Returns (matched_profile_id, bbox, face_image, unknown) where `unknown`
        is None, or (face_image, embedding) for the most prominent *unmatched*
        face — a real, reasonably large face that belongs to nobody enrolled.
        Tiny or low-confidence detections are ignored so a poster in the
        background or a far-off passer-by doesn't count as a visitor.

        We support up to 5 family members — all are checked and the best
        match wins.
        """
        if self.app is None:
            return None, None, None, None

        with self._lock:
            faces = self.app.get(frame)
        if not faces:
            return None, None, None, None

        best_match_id, best_score, best_face = None, -1, None
        for face in faces:
            for profile_id, stored_embedding in stored_embeddings:
                score = self.compare(face.embedding, stored_embedding)
                if score > threshold and score > best_score:
                    best_score, best_match_id, best_face = score, profile_id, face

        if best_match_id:
            print(f"Face matched — profile {best_match_id} (score: {best_score:.3f})")
            return best_match_id, best_face.bbox.astype(int), self._crop(frame, best_face), None

        # Nobody matched: is there a face worth reporting?
        candidates = [
            f for f in faces
            if (f.bbox[2] - f.bbox[0]) >= min_face and float(f.det_score) >= min_det_score
        ]
        if not candidates:
            return None, None, None, None
        biggest = max(candidates, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        return None, None, None, (self._crop(frame, biggest), biggest.embedding)


# Singleton instance
face_engine = FaceEngine()
