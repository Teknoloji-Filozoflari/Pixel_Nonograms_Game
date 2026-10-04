{
  description = "Piksel Nonogram — çevrim dışı mantık bulmacaları";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      eachSystem = nixpkgs.lib.genAttrs systems;
      packageFor = system:
        let pkgs = import nixpkgs { inherit system; };
        in pkgs.callPackage ./packaging/nix/package.nix { };
    in {
      packages = eachSystem (system: {
        pixel-nonograms = packageFor system;
        default = self.packages.${system}.pixel-nonograms;
      });

      apps = eachSystem (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.pixel-nonograms}/bin/pixel-nonograms";
        };
      });

      checks = eachSystem (system:
        let pkgs = import nixpkgs { inherit system; };
        in {
          package = self.packages.${system}.pixel-nonograms;
          smoke = pkgs.runCommand "pixel-nonograms-installed-smoke" {
            nativeBuildInputs = [ self.packages.${system}.pixel-nonograms ];
          } ''
            export QT_QPA_PLATFORM=offscreen
            export QT_QUICK_BACKEND=software
            export XDG_CONFIG_HOME="$TMPDIR/config"
            export XDG_DATA_HOME="$TMPDIR/data"
            export XDG_CACHE_HOME="$TMPDIR/cache"
            export XDG_STATE_HOME="$TMPDIR/state"
            pixel-nonograms --smoke-test
            touch "$out"
          '';
        });
    };
}
