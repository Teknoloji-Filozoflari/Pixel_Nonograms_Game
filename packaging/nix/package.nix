{ lib, python3, qt6, ruff, makeFontsConf, dejavu_fonts }:
let
  project = builtins.fromTOML (builtins.readFile ../../pyproject.toml);
  fonts = makeFontsConf { fontDirectories = [ dejavu_fonts ]; };
in
python3.pkgs.buildPythonApplication {
  pname = "pixel-nonograms";
  version = project.project.version;
  pyproject = true;
  src = lib.cleanSourceWith {
    src = ../..;
    filter = path: type:
      let name = baseNameOf path;
      in lib.cleanSourceFilter path type
        && !(builtins.elem name [ ".venv" ".venv-linux" "build" "dist" "artifacts"
          ".reference" ".pytest_cache" ".ruff_cache" "__pycache__"
          "parts" "stage" "prime" ".snapcraft" "result" ])
        && !(lib.hasSuffix ".egg-info" name)
        && !(lib.hasPrefix "result-" name)
        && !(lib.hasSuffix ".pyc" name)
        && !(lib.hasSuffix ".sqlite3" name);
  };
  # Nixpkgs supplies Essentials through the full PySide6 distribution.
  postPatch = ''
    substituteInPlace pyproject.toml \
      --replace-fail 'PySide6-Essentials>=6.8,<7' 'PySide6>=6.8,<7'
  '';
  build-system = [ python3.pkgs.setuptools ];
  dependencies = with python3.pkgs; [ pyside6 numpy pillow ];
  nativeBuildInputs = [ qt6.wrapQtAppsHook ];
  buildInputs = with qt6; [ qtbase qtsvg qtwayland ];
  dontWrapQtApps = true;
  preFixup = ''
    makeWrapperArgs+=( "''${qtWrapperArgs[@]}" )
    makeWrapperArgs+=( --set FONTCONFIG_FILE "${fonts}" )
  '';
  nativeCheckInputs = [ python3.pkgs.pytest ruff ];
  checkPhase = ''
    runHook preCheck
    export QT_QPA_PLATFORM=offscreen
    export FONTCONFIG_FILE="${fonts}"
    export QT_PLUGIN_PATH="${qt6.qtbase}/${qt6.qtbase.qtPluginPrefix}:${qt6.qtsvg}/${qt6.qtbase.qtPluginPrefix}"
    ruff check src tests tools/build_bundle.py tools/build_rpm.py
    ${python3.interpreter} -m pytest -q
    runHook postCheck
  '';
  postInstall = ''
    install -Dm644 packaging/linux/pixel-nonograms.desktop \
      "$out/share/applications/pixel-nonograms.desktop"
    install -Dm644 packaging/linux/pixel-nonograms.png \
      "$out/share/icons/hicolor/256x256/apps/pixel-nonograms.png"
    install -Dm644 LICENSE "$out/share/doc/pixel-nonograms/LICENSE"
    install -Dm644 THIRD_PARTY_NOTICES.md "$out/share/doc/pixel-nonograms/THIRD_PARTY_NOTICES.md"
  '';
  pythonImportsCheck = [ "pixel_nonograms" "pixel_nonograms.app" ];
  meta = {
    description = "Offline picture logic game with 1000 puzzles";
    homepage = "https://github.com/Teknoloji-Filozoflari/Pixel_Nonograms_Game";
    license = lib.licenses.gpl3Plus;
    platforms = lib.platforms.linux;
    mainProgram = "pixel-nonograms";
  };
}
