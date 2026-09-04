{
  description = "Pinned LineageOS AVD system and KernelSU kernel build environment";
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-26.05";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = import nixpkgs { inherit system; }; in {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [ python3 git git-repo gh ];
        };
      } // nixpkgs.lib.optionalAttrs (nixpkgs.lib.hasSuffix "linux" system) {
        packages.android-env = pkgs.callPackage ./nix/android-fhs.nix { };
        packages.default = self.packages.${system}.android-env;
      });
}
