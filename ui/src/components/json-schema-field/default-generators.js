export const generateDefault = generatorSpec => {
    if( generatorSpec.type === "random" ) {
        // First, use the crypto module to fill a typed array with random numbers
        const randomValues = new Uint8Array((generatorSpec.length || 32) / 2);
        crypto.getRandomValues(randomValues);
        return (
            Array
                .from(randomValues)
                .map(v => v.toString(16).padStart(2, "0"))
                .join("")
        );
    }
    else {
        console.warn(`Invalid default generator '${generatorSpec.type}' - no default generated`);
    }
};
