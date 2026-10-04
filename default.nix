{ pkgs ? import <nixpkgs> {
    config.allowUnfreePredicate = pkg: (pkg.pname or "") == "pixel-nonograms";
  } }:
pkgs.callPackage ./packaging/nix/package.nix { }
