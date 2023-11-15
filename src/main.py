from model.GeoModel import GeoModel
import time

# please do: pip install mesa mesa-geo
if __name__ == "__main__":
    start_time=time.time()
    model = GeoModel(n_doctors=2, n_nurses=3, ocupation=40)
    print(model.counts)
    model.run_model()
    print(model.counts)
    print("--- running for %s seconds ---" % (time.time() - start_time))