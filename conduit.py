import math
import friction
from abc import ABCMeta, abstractmethod

class Conduit:
    __metaclass__ = ABCMeta

    """set step lengths, define defaults"""
    step = (0, 0.625, 0.625, 1.25, 2.5, 2.5, 5, 5, 10,
        10, 10, 10, 10, 10, 10, 10, 2.5)
    g = 9.806   # gravitational constant
    precision = 0.0001
    MAX_ITER = 29

    def __init__(self):
        self.flow = None
    #    self.width = None
    #    self.depth = None
        self.length = None
        self.us_invert = None
        self.ds_invert = None
        self.slope = None
        self.Ks = None
        self.kinvisc = None
        self.ds_depth = None
        self.chainage = []
        self.energy = []
        self.water = []
        self.head = []
        self.crit_depth = 0.0
        self.norm_depth = 0.0
        self.open_chan = None
        self.friction_formula = None



    def setValues(self, flow, length, us_il, ds_il, Ks, kinvisc,
     ds_depth=0, open_chan=True):
        self.flow = self.checkValues(flow, True)
    #    self.width = self.checkValues(width, True)
    #    self.depth = self.checkValues(depth, True)
        self.length = self.checkValues(length, True)
        self.us_invert = self.checkValues(us_il)
        self.ds_invert = self.checkValues(ds_il)
        self.slope = (self.us_invert - self.ds_invert) / self.length
        self.Ks = self.checkValues(Ks, True)
        self.kinvisc = self.checkValues(kinvisc, True)
        self.ds_depth = self.checkValues(ds_depth, True)
        self.open_chan = open_chan
        self.friction_formula = friction.DarcyWeisbach(self.Ks, self.kinvisc)

    def checkValues(self, checkValue, non_negative=False):
        # change to static method
        try:
            checkValue = float(checkValue)
            if non_negative:
                if checkValue < 0:
                    raise ValueError("Can't be negative")
        except ValueError as e:
            print("can't be negative", e)
            pass
        return checkValue

    @abstractmethod
    def critical_depth(self):
        """calculate critical depth for channel"""
        pass

    @abstractmethod
    def max_depth(self):
        pass

    @abstractmethod
    def getFlowArea(self, depth):
        pass

    @abstractmethod
    def getFlowPerimeter(self, depth):
        pass

    @abstractmethod
    def conduitArea(self):
        pass

    @abstractmethod
    def conduitPerimeter(self):
        pass

    def normal_depth(self):
        """calculate normal depth for channel"""
        # check for flat slope
        if self.slope <= 0.0001:
            raise ValueError("check slope")
        upper = self.max_depth()
        lower = 0.0
        solution = False
        while not solution:
            normal_depth = (upper + lower) / 2.0
            area = self.getFlowArea(normal_depth)
            perimeter = self.getFlowPerimeter(normal_depth)
            vel_norm = self.flow / area
            hydraulic_radius = area / perimeter
            friction_factor = self.friction_formula.friction_factor(
                hydraulic_radius, vel_norm)
            calc_flow = math.pow((self.slope * 4.0 * hydraulic_radius *
                area * area * 2.0 * Conduit.g / friction_factor), 0.5)
            if math.fabs(self.flow - calc_flow) < Conduit.precision:
                solution = True
            elif calc_flow > self.flow:
                upper = normal_depth
            else:
                lower = normal_depth
        return normal_depth

    def backwater(self):
        """calculate back water profile. Calculate zero distance values,
         then distances as per step length."""
        water_depth = max(self.ds_depth, self.crit_depth)
        E_previous = 0
        Sf_previous = 0
        delta_chain = 0
        previous_depth = water_depth
        for i in Conduit.step:
            if i == 0:
                # check for conduit full
                if water_depth > self.max_depth():
                    wet_perimeter = self.conduitPerimeter()
                    area = self.conduitArea()
                else:
                    wet_perimeter = self.getFlowPerimeter(water_depth)
                    area = self.getFlowArea(water_depth)
                hyd_radius = area / wet_perimeter
                velocity = self.flow / area
                E0 = water_depth + (velocity**2 / (2 * Conduit.g))
                # Sf = slope of hydraulic gradient
                Sf = self.friction_formula.frictionSlope(hyd_radius, velocity)
                # print("E0: %.3f" % E0, " Sf: %.3f" % Sf)
                E_previous = E0
                Sf_previous = Sf
                self.updateResults(0, E0, water_depth)
            elif water_depth >= self.max_depth():
                delta_L = i * (self.length / 100.0)
                # print(delta_L, water_depth)
                wet_perimeter = self.conduitPerimeter()
                area = self.conduitArea()
                hyd_radius = area / wet_perimeter
                velocity = self.flow / area
                E0 = water_depth + (velocity**2 / (2 * Conduit.g))
                # print(E0)
                Sf = self.friction_formula.frictionSlope(hyd_radius, velocity)
                E_upstream = E0 + delta_L * Sf
                water_depth = E_upstream - velocity**2 / (2 * Conduit.g)
                # print(water_depth)
                E_previous = E_upstream
                E2 = E_previous
                Sf_previous = Sf
                previous_depth = water_depth
                delta_chain += delta_L
                self.updateResults(delta_chain, E2, water_depth)
            else:
                delta_L = i * (self.length / 100.0)
                upper = self.max_depth()
                lower = previous_depth

                solution = False
                count = 0
                while not solution:
                    water_depth = (upper + lower) / 2.0
                    area = self.getFlowArea(water_depth)
                    wet_perimeter = self.getFlowPerimeter(water_depth)
                    hyd_radius = area / wet_perimeter
                    velocity = self.flow / area
                    E_upstream = water_depth + (velocity**2 / (2 * Conduit.g))
                    Sf = self.friction_formula.frictionSlope(hyd_radius, velocity)
                    Sf_mean = (Sf + Sf_previous) / 2.0
                    E2 = E_previous - delta_L * (self.slope - Sf_mean)
                    # print("check", E_upstream, E2)
                    if math.fabs(E_upstream - E2) < Conduit.precision:
                        solution = True
                    elif E_upstream > E2:
                        upper = water_depth
                        count += 1
                        if count == Conduit.MAX_ITER:
                            solution = True
                    else:
                        lower = water_depth
                        count += 1
                        if count == Conduit.MAX_ITER:
                            solution = True
                E_previous = E2
                Sf_previous = Sf
                previous_depth = water_depth
                delta_chain += delta_L
                self.updateResults(delta_chain, E2, water_depth)
                # print("Friction: %.4f" % friction_factor)
                # print("Length %.1f" % delta_chain, "E2: %.3f" % E_previous, " Sf: %.3f" % Sf_previous)
        return E2

    def updateResults(self, delta_chain, energy, water_depth):
        self.chainage.append(delta_chain)
        self.energy.append(self.ds_invert + delta_chain * self.slope + energy)
        self.water.append(water_depth)
        self.head.append(self.ds_invert +
            delta_chain * self.slope + water_depth)

    def clearResults(self):
        del self.chainage[:]
        del self.energy[:]
        del self.water[:]
        del self.head[:]

    def calculate(self):
        try:
            # TODO validate data
            # calculate critical depth
            self.crit_depth = self.critical_depth()
            # calculate normal depth
            self.norm_depth = self.normal_depth()
            # print(self.slope)
            # TODO figure out how to handle downstream depth greater than normal depth
    #        if self.ds_depth > self.norm_depth:
    #            return
            if self.norm_depth > self.crit_depth:
                self.clearResults()
                self.backwater()
        except ValueError as e:
            print(e)
            pass
        except:
            pass


#main
#"""enter flow, width, depth, length, us invert, ds invert, Ks, kinematic viscocity"""
#channel1 = Channel(0.5, 0.8, 2.0, 100, 1.0, 0.9, 0.003, 1.141e-06)
#print(channel1.critical_depth())
#print(channel1.normal_depth())
#crit_depth = channel1.critical_depth()
#channel1.backwater(crit_depth)
#print(channel1.chainage[0], channel1.energy[0], channel1.water[0], channel1.head[0])
#x = 0
#for i in channel1.chainage:
#    print("Length %.1f" % i, "Energy %.3f" % channel1.energy[x], "Water %.3f" % channel1.water[x], "Head %.3f" % channel1.head[x])
#    x += 1