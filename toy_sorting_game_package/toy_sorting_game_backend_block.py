# =========================
# Toy Sorting Game — Librarian + Toy Store Worker bridge activity
# Frontend routes:
#   /api/toy-sorting-game/tts
#   /api/toy-sorting-game/transcribe
#   /api/toy-sorting-game/complete
#
# Put this block in app.py near your other game backend blocks.
# Requires:
#   templates/toy_sorting_game.html
#   static/css/toy_sorting_game.css
#   static/js/toy_sorting_game.js
# =========================

def sanitize_toy_sorting_line(text, fallback="Nice sorting.", max_len=260):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    text = text.replace('"', "")[:max_len]

    if not text:
        return fallback

    banned_terms = [
        "selective mutism",
        "anxiety",
        "therapy",
        "treatment",
        "exposure",
        "diagnosis",
        "progress",
        "bravery",
        "confidence",
        "use your words"
    ]

    lowered = text.lower()

    if any(term in lowered for term in banned_terms):
        return fallback

    return text


def generate_toy_sorting_voice_elevenlabs(text, speaker="librarian", game_complete=False):
    speaker = str(speaker or "librarian").strip().lower()

    if speaker == "toyworker":
        voice_id = (
            os.getenv("TOY_WORKER_VOICE_ID")
            or os.getenv("TOY_TRIVIA_VOICE_ID")
            or os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
        )
        voice_settings = {
            "stability": 0.94,
            "similarity_boost": 0.90,
            "style": 0.06,
            "use_speaker_boost": False
        }
    else:
        voice_id = (
            os.getenv("LIBRARIAN_VOICE_ID")
            or os.getenv("BOOK_GUESSING_VOICE_ID")
            or os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
        )
        voice_settings = {
            "stability": 0.94,
            "similarity_boost": 0.90,
            "style": 0.04,
            "use_speaker_boost": False
        }

    if game_complete:
        voice_settings["style"] = max(voice_settings.get("style", 0), 0.12)

    response = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings=voice_settings
    )

    return b"".join(response)


@app.route("/api/toy-sorting-game/tts", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("60 per minute")
def toy_sorting_game_tts():
    data = request.get_json(silent=True) or {}

    speaker = str(data.get("speaker", "librarian")).strip().lower()
    text = sanitize_toy_sorting_line(data.get("text", ""), fallback="Nice sorting.")

    if speaker not in {"librarian", "toyworker"}:
        speaker = "librarian"

    if not text:
        return jsonify({"success": False, "error": "Missing text"}), 400

    try:
        audio_bytes = generate_toy_sorting_voice_elevenlabs(text, speaker=speaker)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return jsonify({
            "success": True,
            "speaker": speaker,
            "message": text,
            "audio": f"data:audio/mpeg;base64,{audio_base64}"
        })

    except Exception as e:
        print("Toy sorting TTS error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not generate toy sorting audio"
        }), 500


@app.route("/api/toy-sorting-game/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def toy_sorting_game_transcribe():
    if "audio" not in request.files:
        return jsonify({
            "success": False,
            "error": "Missing audio"
        }), 400

    audio_file = request.files["audio"]

    try:
        import io

        audio_bytes = audio_file.read()

        if not audio_bytes:
            return jsonify({
                "success": False,
                "error": "Empty audio file"
            }), 400

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = "toy-sorting-response.webm"

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj
        )

        text = transcript.text.strip()
        print("TOY SORTING TRANSCRIPT:", text)

        return jsonify({
            "success": True,
            "text": text
        })

    except Exception as e:
        print("Toy sorting transcription error:", repr(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/toy-sorting-game/complete", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("20 per minute")
def toy_sorting_game_complete():
    data = request.get_json(silent=True) or {}

    try:
        activity_id = int(data.get("activity_id") or 4)
        words_spoken = max(0, int(float(data.get("words_spoken", 0) or 0)))
        minutes_spoken = max(0.0, float(data.get("minutes_spoken", 0) or 0))
        active_minutes = max(0.0, float(data.get("active_minutes", 0) or 0))
        time_spent = max(
            0.0,
            float(data.get("time_spent_on_activity", active_minutes) or active_minutes)
        )
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid completion data"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT activity_id, scene_id, activity_order
            FROM activity
            WHERE activity_id = ? AND is_active = 1
        """, (activity_id,))

        activity = cursor.fetchone()

        if not activity:
            conn.close()
            return jsonify({"success": False, "error": "Activity not found"}), 404

        cursor.execute("""
            INSERT OR IGNORE INTO progress (
                user_id,
                activity_id,
                is_unlocked,
                is_completed,
                words_spoken,
                minutes_spoken,
                active_minutes,
                time_spent_on_activity
            )
            VALUES (?, ?, 1, 0, 0, 0, 0, 0)
        """, (session["user_id"], activity_id))

        cursor.execute("""
            UPDATE progress
            SET
                is_completed = 1,
                completed_at = CURRENT_TIMESTAMP,
                words_spoken = COALESCE(words_spoken, 0) + ?,
                minutes_spoken = COALESCE(minutes_spoken, 0) + ?,
                active_minutes = COALESCE(active_minutes, 0) + ?,
                time_spent_on_activity = COALESCE(time_spent_on_activity, 0) + ?
            WHERE user_id = ? AND activity_id = ?
        """, (
            words_spoken,
            minutes_spoken,
            active_minutes,
            time_spent,
            session["user_id"],
            activity_id
        ))

        cursor.execute("""
            INSERT INTO session_log (
                user_id,
                activity_id,
                words_spoken,
                minutes_spoken,
                active_minutes,
                completed_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            session["user_id"],
            activity_id,
            words_spoken,
            minutes_spoken,
            active_minutes
        ))

        cursor.execute("""
            SELECT activity_id
            FROM activity
            WHERE is_active = 1
              AND (
                scene_id > ?
                OR (scene_id = ? AND activity_order > ?)
              )
            ORDER BY scene_id ASC, activity_order ASC
            LIMIT 1
        """, (
            activity["scene_id"],
            activity["scene_id"],
            activity["activity_order"]
        ))

        next_activity = cursor.fetchone()
        next_activity_id = None

        if next_activity:
            next_activity_id = next_activity["activity_id"]

            cursor.execute("""
                INSERT OR IGNORE INTO progress (
                    user_id,
                    activity_id,
                    is_unlocked,
                    is_completed,
                    words_spoken,
                    minutes_spoken,
                    active_minutes,
                    time_spent_on_activity
                )
                VALUES (?, ?, 1, 0, 0, 0, 0, 0)
            """, (session["user_id"], next_activity_id))

            cursor.execute("""
                UPDATE progress
                SET is_unlocked = 1
                WHERE user_id = ? AND activity_id = ?
            """, (session["user_id"], next_activity_id))

            cursor.execute("""
                UPDATE users
                SET current_activity_id = ?
                WHERE user_id = ?
            """, (next_activity_id, session["user_id"]))

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "next_activity_id": next_activity_id
        })

    except Exception as e:
        conn.rollback()
        conn.close()
        print("Toy sorting completion error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not save toy sorting completion"
        }), 500
