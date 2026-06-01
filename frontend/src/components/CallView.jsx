import { useEffect, useRef, useState } from 'react';
import { Room, RoomEvent, Track } from 'livekit-client';
import { useStore } from '../store';
import { initials, colorFor } from './ui';

// A floating call window backed by a LiveKit room. Persists across channel
// switches so you can keep talking while browsing.
export default function CallView() {
  const { activeCall, leaveCall, channels } = useStore();
  const roomRef = useRef(null);
  const [tick, setTick] = useState(0); // bump to re-render on room events
  const [error, setError] = useState('');
  const [status, setStatus] = useState('connecting');
  const [micOn, setMicOn] = useState(true);
  const [camOn, setCamOn] = useState(true);
  const [sharing, setSharing] = useState(false);

  const channel = channels.find((c) => c.id === activeCall?.channelId);

  useEffect(() => {
    let cancelled = false;
    const room = new Room({ adaptiveStream: true, dynacast: true });
    roomRef.current = room;

    const bump = () => !cancelled && setTick((t) => t + 1);
    room
      .on(RoomEvent.ParticipantConnected, bump)
      .on(RoomEvent.ParticipantDisconnected, bump)
      .on(RoomEvent.TrackSubscribed, bump)
      .on(RoomEvent.TrackUnsubscribed, bump)
      .on(RoomEvent.LocalTrackPublished, bump)
      .on(RoomEvent.LocalTrackUnpublished, bump)
      .on(RoomEvent.Disconnected, () => !cancelled && setStatus('disconnected'));

    (async () => {
      try {
        const iceServers = activeCall.iceServers?.length
          ? { rtcConfig: { iceServers: activeCall.iceServers } }
          : {};
        await room.connect(activeCall.url, activeCall.token, iceServers);
        if (cancelled) return;
        setStatus('connected');
        await room.localParticipant.setMicrophoneEnabled(true);
        await room.localParticipant.setCameraEnabled(true);
        bump();
      } catch (e) {
        if (!cancelled) {
          setError(e?.message || 'Could not connect to the call server.');
          setStatus('error');
        }
      }
    })();

    return () => {
      cancelled = true;
      room.disconnect();
      roomRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeCall?.channelId]);

  const toggleMic = async () => {
    const next = !micOn;
    await roomRef.current?.localParticipant.setMicrophoneEnabled(next);
    setMicOn(next);
  };
  const toggleCam = async () => {
    const next = !camOn;
    await roomRef.current?.localParticipant.setCameraEnabled(next);
    setCamOn(next);
  };
  const toggleShare = async () => {
    const next = !sharing;
    try {
      await roomRef.current?.localParticipant.setScreenShareEnabled(next);
      setSharing(next);
    } catch {
      /* user cancelled the picker */
    }
  };
  const hangUp = () => {
    roomRef.current?.disconnect();
    leaveCall();
  };

  const room = roomRef.current;
  const participants = room
    ? [room.localParticipant, ...room.remoteParticipants.values()]
    : [];

  return (
    <div className="call-overlay">
      <div className="call-head">
        <span>
          📞 Call · {channel?.isDm ? channel.name : `#${channel?.name || ''}`}
          {status === 'connecting' && ' — connecting…'}
        </span>
        <button className="call-x" onClick={hangUp} title="Leave call">
          ✕
        </button>
      </div>

      {error ? (
        <div className="call-error">
          <p>⚠️ {error}</p>
          <p className="hint">
            Is the LiveKit server reachable? See the README "Calls" section.
          </p>
        </div>
      ) : (
        <div className={`call-grid count-${Math.min(participants.length, 4)}`}>
          {participants.map((p) => (
            <ParticipantTile
              key={p.sid || p.identity}
              participant={p}
              isLocal={p === room.localParticipant}
              tick={tick}
            />
          ))}
        </div>
      )}

      <div className="call-controls">
        <button className={micOn ? '' : 'off'} onClick={toggleMic} title="Mic">
          {micOn ? '🎤' : '🔇'}
        </button>
        <button className={camOn ? '' : 'off'} onClick={toggleCam} title="Camera">
          {camOn ? '📹' : '🚫'}
        </button>
        <button
          className={sharing ? 'active' : ''}
          onClick={toggleShare}
          title="Share screen"
        >
          🖥️
        </button>
        <button className="hangup" onClick={hangUp} title="Leave">
          📞 Leave
        </button>
      </div>
    </div>
  );
}

function ParticipantTile({ participant, isLocal, tick }) {
  const videoRef = useRef(null);
  const audioRef = useRef(null);

  useEffect(() => {
    const pubs = Array.from(participant.trackPublications.values());
    const screen = pubs.find(
      (p) => p.source === Track.Source.ScreenShare && p.track
    );
    const cam = pubs.find((p) => p.source === Track.Source.Camera && p.track);
    const videoTrack = (screen || cam)?.track;
    if (videoTrack && videoRef.current) videoTrack.attach(videoRef.current);

    let audioTrack;
    if (!isLocal) {
      audioTrack = pubs.find((p) => p.kind === 'audio' && p.track)?.track;
      if (audioTrack && audioRef.current) audioTrack.attach(audioRef.current);
    }

    return () => {
      if (videoTrack && videoRef.current) videoTrack.detach(videoRef.current);
      if (audioTrack && audioRef.current) audioTrack.detach(audioRef.current);
    };
  }, [participant, tick, isLocal]);

  const name = participant.name || participant.identity;
  const hasVideo = Array.from(participant.trackPublications.values()).some(
    (p) => p.kind === 'video' && p.track && !p.isMuted
  );

  return (
    <div className="call-tile">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted={isLocal}
        style={{ display: hasVideo ? 'block' : 'none' }}
      />
      {!hasVideo && (
        <div className="call-novideo" style={{ background: colorFor(name.length) }}>
          {initials(name)}
        </div>
      )}
      {!isLocal && <audio ref={audioRef} autoPlay />}
      <span className="call-name">
        {name}
        {isLocal && ' (you)'}
      </span>
    </div>
  );
}
