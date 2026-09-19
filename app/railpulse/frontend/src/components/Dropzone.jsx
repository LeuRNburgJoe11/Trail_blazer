import { useRef, useState } from "react";

export default function Dropzone({ accept, multiple, hint, onFilesSelected }) {
  const inputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);
  const [selected, setSelected] = useState([]);

  function handleFiles(fileList) {
    const files = Array.from(fileList);
    setSelected(files);
    onFilesSelected(files);
  }

  return (
    <div>
      <div
        className={`dropzone${dragActive ? " dropzone--active" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          handleFiles(e.dataTransfer.files);
        }}
      >
        <p className="dropzone__title">Drop file(s) here, or click to browse</p>
        <p className="dropzone__hint">{hint}</p>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {selected.length > 0 && (
        <p className="dropzone__selected">
          {selected.length} file{selected.length > 1 ? "s" : ""} selected: {selected.map((f) => f.name).join(", ")}
        </p>
      )}
    </div>
  );
}
