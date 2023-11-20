from model.GeoModel import GeoModel
import time

# please do: pip install mesa mesa-geo
if __name__ == "__main__":
    model = GeoModel(n_doctors=2, n_nurses=3, ocupation=40)
    print('model initialized')
    print(model.counts)
    start_time=time.time()
    print('started running model at %s'%start_time)
    model.run_model()
    print("--- running for %s seconds ---" % (time.time() - start_time))
    print(model.counts)