# face_utils.py

import os
import numpy as np
import face_recognition
from django.conf import settings
from django.core.exceptions import ValidationError

def generate_face_embedding(image_path, username):
    try:
        print(f"[INFO] Generating embedding for user: {username}")
        
        image = face_recognition.load_image_file(image_path)
        face_locations = face_recognition.face_locations(image)

        if not face_locations:
            raise ValidationError("No face detected in the uploaded image.")

        face_encodings = face_recognition.face_encodings(image, face_locations)

        if not face_encodings:
            raise ValidationError("Failed to extract face encoding.")

        embedding = face_encodings[0]  # Use the first detected face
        embedding_filename = f"{username}_embedding.npy"

        embedding_dir = os.path.join(settings.MEDIA_ROOT, "face_embeddings")
        os.makedirs(embedding_dir, exist_ok=True)

        embedding_path = os.path.join(embedding_dir, embedding_filename)
        np.save(embedding_path, embedding)

        print("[SUCCESS] Face embedding saved at:", embedding_path)
        return embedding_filename, embedding_path

    except Exception as e:
        raise RuntimeError(f"Error generating face embedding: {e}")
